import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.api import dashboard, playlists, spotify, sync, youtube
from app.core.config import settings
from app.core.errors import ExternalResponseError
from app.core.logging import configure_logging, logger

configure_logging()

app = FastAPI(title="SyncTune")

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(spotify.router)
app.include_router(youtube.router)
app.include_router(sync.router)
app.include_router(dashboard.router)
app.include_router(playlists.router)


@app.exception_handler(httpx.HTTPStatusError)
async def external_api_error_handler(request: Request, exc: httpx.HTTPStatusError) -> JSONResponse:
    """Catch-all for unhandled failures calling Spotify/YouTube (spec §41:
    never show a raw HTTP code as the only message). Endpoints that need a
    more specific/actionable message (e.g. VideoNotFoundError, expired
    token) still catch their own exceptions before this ever runs — this
    only covers what nothing more specific caught.
    """
    status = exc.response.status_code
    if status == 429:
        detail = "Spotify o YouTube están limitando las solicitudes por ahora. Esperá un momento y probá de nuevo."
    elif status in (401, 403):
        detail = "No pudimos completar la operación — puede que la conexión haya expirado. Reconectá tu cuenta."
    else:
        detail = "Uno de los servicios externos (Spotify o YouTube) no respondió correctamente. Probá de nuevo."
    logger.warning("external_api_error", extra={"status": status, "path": request.url.path})
    return JSONResponse(status_code=502, content={"detail": detail})


@app.exception_handler(ExternalResponseError)
async def external_response_error_handler(request: Request, exc: ExternalResponseError) -> JSONResponse:
    """Spotify/YouTube answered OK but with a shape we don't understand
    (an API change). Logged with the detail for us; the user gets a
    plain-language message, never a stack trace."""
    logger.error("external_response_unexpected", extra={"path": request.url.path, "detail": str(exc)})
    return JSONResponse(
        status_code=502,
        content={"detail": "Spotify o YouTube respondieron algo que no esperábamos. Probá de nuevo en un rato."},
    )
