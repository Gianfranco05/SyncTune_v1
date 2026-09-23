import secrets
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import encrypt
from app.core.database import get_db
from app.core.security import get_valid_access_token
from app.models import Connection, Provider, User
from app.schemas.playlist import PlaylistTrack
from app.schemas.spotify import (
    AddTrackRequest,
    CreatePlaylistRequest,
    Playlist,
    SpotifyMe,
)
from app.services import spotify_service

router = APIRouter(prefix="/api/spotify", tags=["spotify"])


@router.get("/login")
async def login(request: Request):
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    return RedirectResponse(spotify_service.build_auth_url(state))


@router.get("/callback")
async def callback(
    request: Request,
    db: Session = Depends(get_db),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    if error:
        return RedirectResponse(f"{settings.frontend_origin}/?spotify_error={error}")

    expected_state = request.session.get("oauth_state")
    if not code or not state or state != expected_state:
        raise HTTPException(status_code=400, detail="Estado OAuth inválido")

    try:
        tokens = await spotify_service.exchange_code_for_tokens(code)
        profile = await spotify_service.get_current_user(tokens["access_token"])
    except httpx.HTTPStatusError:
        return RedirectResponse(f"{settings.frontend_origin}/?spotify_error=oauth_failed")
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])

    connection = db.scalar(
        select(Connection).where(
            Connection.provider == Provider.spotify,
            Connection.provider_account_id == profile["id"],
        )
    )
    if connection:
        user_id = connection.user_id
    else:
        user = User()
        db.add(user)
        db.flush()
        connection = Connection(
            user_id=user.id,
            provider=Provider.spotify,
            provider_account_id=profile["id"],
        )
        db.add(connection)
        user_id = user.id

    connection.display_name = profile.get("display_name")
    connection.access_token = encrypt(tokens["access_token"])
    connection.refresh_token = encrypt(tokens["refresh_token"])
    connection.expires_at = expires_at
    db.commit()

    request.session.clear()
    request.session["user_id"] = user_id
    return RedirectResponse(settings.frontend_origin)


@router.get("/me", response_model=SpotifyMe)
def me(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return SpotifyMe(authenticated=False)

    connection = db.scalar(
        select(Connection).where(Connection.user_id == user_id, Connection.provider == Provider.spotify)
    )
    if not connection:
        return SpotifyMe(authenticated=False)

    return SpotifyMe(authenticated=True, id=connection.provider_account_id, display_name=connection.display_name)


@router.post("/logout")
async def logout(request: Request):
    """Ends this browser session only — the stored connection is kept.

    See POST /disconnect for actually revoking/removing the Spotify
    connection (spec §59, privacy).
    """
    request.session.clear()
    return {"ok": True}


@router.post("/disconnect")
def disconnect(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if user_id:
        connection = db.scalar(
            select(Connection).where(Connection.user_id == user_id, Connection.provider == Provider.spotify)
        )
        if connection:
            db.delete(connection)
            db.commit()
    request.session.clear()
    return {"ok": True}


@router.get("/search", response_model=list[PlaylistTrack])
async def search(
    q: str = Query(min_length=1, max_length=200),
    access_token: str = Depends(get_valid_access_token),
):
    """Free-text track search, for picking a match by hand when none of the
    automatic candidates is right (spec §9: "buscar manualmente")."""
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Escribí algo para buscar.")
    return await spotify_service.search_tracks(access_token, query, limit=10)


@router.get("/playlists", response_model=list[Playlist])
async def list_playlists(access_token: str = Depends(get_valid_access_token)):
    return await spotify_service.get_user_playlists(access_token)


@router.post("/playlists", response_model=Playlist)
async def new_playlist(body: CreatePlaylistRequest, access_token: str = Depends(get_valid_access_token)):
    return await spotify_service.create_playlist(access_token, body.name)


@router.post("/playlists/{playlist_id}/tracks")
async def add_track(
    playlist_id: str,
    body: AddTrackRequest,
    access_token: str = Depends(get_valid_access_token),
):
    await spotify_service.add_track_to_playlist(access_token, playlist_id, body.track_uri)
    return {"ok": True}
