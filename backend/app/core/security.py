"""Centralizes OAuth token lifecycle handling for both providers.

    token válido -> usar token
    token expirado -> refresh token -> nuevo access token

Tokens live in the `connections` table (encrypted, see core/crypto.py), keyed
by the user id stored in the session cookie — the cookie itself never holds
a token. Spotify is the "primary" login (it's what creates the User row);
YouTube is always a connection ADDED to an already-logged-in user (FASE 5).
"""

from datetime import datetime, timedelta, timezone
from typing import Callable

import httpx
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt, encrypt
from app.core.database import get_db
from app.core.logging import logger
from app.models import Connection, Provider
from app.services import spotify_service, youtube_service

_NOT_AUTHENTICATED_DETAIL = {
    Provider.spotify: "No autenticado con Spotify",
    Provider.youtube: "No autenticado con YouTube",
}

_RECONNECT_DETAIL = {
    Provider.spotify: "Tu conexión con Spotify expiró. Reconectá tu cuenta para seguir.",
    Provider.youtube: "Tu conexión con YouTube expiró. Reconectá tu cuenta para seguir.",
}

_REFRESH_FUNCS: dict[Provider, Callable] = {
    Provider.spotify: spotify_service.refresh_access_token,
    Provider.youtube: youtube_service.refresh_access_token,
}


def require_session_user_id(request: Request) -> int:
    """Any logged-in session (today: always created via Spotify login)."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Iniciá sesión con Spotify primero.")
    return user_id


def _connection_dependency(provider: Provider) -> Callable[..., Connection]:
    def _get(request: Request, db: Session = Depends(get_db)) -> Connection:
        user_id = request.session.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail=_NOT_AUTHENTICATED_DETAIL[provider])

        connection = db.scalar(
            select(Connection).where(Connection.user_id == user_id, Connection.provider == provider)
        )
        if not connection:
            raise HTTPException(status_code=401, detail=_NOT_AUTHENTICATED_DETAIL[provider])

        return connection

    return _get


get_current_spotify_connection = _connection_dependency(Provider.spotify)
get_current_youtube_connection = _connection_dependency(Provider.youtube)


def _access_token_dependency(get_connection: Callable[..., Connection]) -> Callable[..., str]:
    async def _get(
        connection: Connection = Depends(get_connection),
        db: Session = Depends(get_db),
    ) -> str:
        if datetime.now(timezone.utc) >= connection.expires_at:
            refresh = _REFRESH_FUNCS[connection.provider]
            try:
                refreshed = await refresh(decrypt(connection.refresh_token))
            except httpx.HTTPStatusError:
                # Never shown to the user as a raw HTTP code (spec §41) —
                # e.g. Google's unverified-app refresh tokens expire after
                # 7 days (docs/EVOLUTION_PLAN.md §3), so this is expected,
                # not exceptional.
                logger.warning(
                    "token_refresh_failed", extra={"provider": connection.provider.value, "user_id": connection.user_id}
                )
                raise HTTPException(status_code=401, detail=_RECONNECT_DETAIL[connection.provider])
            connection.access_token = encrypt(refreshed["access_token"])
            connection.expires_at = datetime.now(timezone.utc) + timedelta(seconds=refreshed["expires_in"])
            if "refresh_token" in refreshed:
                connection.refresh_token = encrypt(refreshed["refresh_token"])
            db.add(connection)
            db.commit()

        return decrypt(connection.access_token)

    return _get


get_valid_access_token = _access_token_dependency(get_current_spotify_connection)
get_valid_youtube_access_token = _access_token_dependency(get_current_youtube_connection)


def get_current_user_id(connection: Connection = Depends(get_current_spotify_connection)) -> int:
    return connection.user_id
