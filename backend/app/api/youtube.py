"""YouTube/Google OAuth — spec §5. Mirrors api/spotify.py's pattern, with
one key difference: connecting YouTube always links to the user already
logged in via Spotify (require_session_user_id) instead of creating a new
user — Spotify is the app's primary identity provider.
"""

import secrets
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import encrypt
from app.core.database import get_db
from app.core.security import get_valid_youtube_access_token, require_session_user_id
from app.models import Connection, Provider
from app.schemas.youtube import YoutubeMe, YoutubePlaylist
from app.services import youtube_service

router = APIRouter(prefix="/api/youtube", tags=["youtube"])


@router.get("/login")
def login(request: Request, user_id: int = Depends(require_session_user_id)):
    state = secrets.token_urlsafe(16)
    request.session["youtube_oauth_state"] = state
    try:
        return RedirectResponse(youtube_service.build_auth_url(state))
    except youtube_service.GoogleOAuthNotConfiguredError as e:
        raise HTTPException(status_code=501, detail=str(e))


@router.get("/callback")
async def callback(
    request: Request,
    db: Session = Depends(get_db),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    if error:
        return RedirectResponse(f"{settings.frontend_origin}/?youtube_error={error}")

    expected_state = request.session.get("youtube_oauth_state")
    if not code or not state or state != expected_state:
        raise HTTPException(status_code=400, detail="Estado OAuth inválido")

    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Iniciá sesión con Spotify antes de conectar YouTube.")

    try:
        tokens = await youtube_service.exchange_code_for_tokens(code)
        channel = await youtube_service.get_current_user(tokens["access_token"])
    except youtube_service.ChannelNotFoundError:
        return RedirectResponse(f"{settings.frontend_origin}/?youtube_error=no_channel")
    except httpx.HTTPStatusError:
        return RedirectResponse(f"{settings.frontend_origin}/?youtube_error=oauth_failed")

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])

    connection = db.scalar(
        select(Connection).where(
            Connection.provider == Provider.youtube,
            Connection.provider_account_id == channel["id"],
        )
    )
    if not connection:
        connection = Connection(user_id=user_id, provider=Provider.youtube, provider_account_id=channel["id"])
        db.add(connection)
    else:
        # Re-link to the current session's user — see docs/EVOLUTION_PLAN.md
        # §7 (accepted edge case for a ≤5-user personal app).
        connection.user_id = user_id

    connection.display_name = channel["display_name"]
    connection.access_token = encrypt(tokens["access_token"])
    connection.refresh_token = encrypt(tokens["refresh_token"])
    connection.expires_at = expires_at
    db.commit()

    return RedirectResponse(settings.frontend_origin)


@router.get("/status", response_model=YoutubeMe)
def status(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return YoutubeMe(authenticated=False)

    connection = db.scalar(
        select(Connection).where(Connection.user_id == user_id, Connection.provider == Provider.youtube)
    )
    if not connection:
        return YoutubeMe(authenticated=False)

    return YoutubeMe(authenticated=True, id=connection.provider_account_id, display_name=connection.display_name)


@router.get("/playlists", response_model=list[YoutubePlaylist])
async def my_playlists(access_token: str = Depends(get_valid_youtube_access_token)):
    return await youtube_service.fetch_my_playlists(access_token)


@router.post("/disconnect")
def disconnect(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if user_id:
        connection = db.scalar(
            select(Connection).where(Connection.user_id == user_id, Connection.provider == Provider.youtube)
        )
        if connection:
            db.delete(connection)
            db.commit()
    return {"ok": True}
