from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import get_current_user_id, get_valid_access_token, get_valid_youtube_access_token
from app.models import Sync, SyncStatus
from app.schemas.sync import (
    PlaylistConfirmRequest,
    PlaylistPreviewItem,
    PlaylistPreviewRequest,
    PlaylistPreviewResponse,
    SyncConfirmRequest,
    SyncOut,
    SyncPreviewRequest,
    SyncPreviewResponse,
)
from app.services import sync_service, youtube_service

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/preview", response_model=SyncPreviewResponse)
async def preview(
    body: SyncPreviewRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
    access_token: str = Depends(get_valid_access_token),
):
    try:
        result = await sync_service.analyze_youtube_video(access_token, body.youtube_url)
    except ValueError:
        raise HTTPException(status_code=400, detail="El enlace no parece ser una URL válida de YouTube.")
    except youtube_service.VideoNotFoundError:
        raise HTTPException(status_code=404, detail="No encontramos ese video en YouTube.")

    sync = sync_service.create_pending_sync(db, user_id, result["video"])
    return SyncPreviewResponse(sync_id=sync.id, video=result["video"], candidates=result["candidates"])


@router.post("/{sync_id}/confirm", response_model=SyncOut)
async def confirm(
    sync_id: int,
    body: SyncConfirmRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
    access_token: str = Depends(get_valid_access_token),
):
    sync = db.get(Sync, sync_id)
    if not sync or sync.user_id != user_id:
        raise HTTPException(status_code=404, detail="Sincronización no encontrada.")
    if sync.status == SyncStatus.completed:
        raise HTTPException(status_code=409, detail="Esta sincronización ya fue confirmada.")

    track = {
        "id": body.track_id,
        "uri": body.track_uri,
        "name": body.track_name,
        "artists": body.track_artists,
        "confidence": body.confidence,
    }
    return await sync_service.confirm_sync(db, sync, access_token, track, body.playlist_id, body.playlist_name)


@router.post("/playlist/preview", response_model=PlaylistPreviewResponse)
async def preview_playlist(
    body: PlaylistPreviewRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
    spotify_token: str = Depends(get_valid_access_token),
    youtube_token: str = Depends(get_valid_youtube_access_token),
):
    try:
        result = await sync_service.analyze_youtube_playlist(spotify_token, youtube_token, body.youtube_url)
    except ValueError:
        raise HTTPException(status_code=400, detail="El enlace no parece ser una URL de playlist de YouTube válida.")
    except youtube_service.PlaylistNotFoundError:
        raise HTTPException(status_code=404, detail="No encontramos esa playlist en YouTube.")

    sync, item_ids = sync_service.create_pending_playlist_sync(db, user_id, result["title"], result["items"])
    return PlaylistPreviewResponse(
        sync_id=sync.id,
        playlist_title=result["title"],
        total_video_count=result["total_video_count"],
        truncated=result["truncated"],
        items=[
            PlaylistPreviewItem(item_id=item_id, video=entry["video"], candidates=entry["candidates"])
            for item_id, entry in zip(item_ids, result["items"])
        ],
    )


@router.post("/{sync_id}/playlist/confirm", response_model=SyncOut)
async def confirm_playlist(
    sync_id: int,
    body: PlaylistConfirmRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
    access_token: str = Depends(get_valid_access_token),
):
    sync = db.get(Sync, sync_id)
    if not sync or sync.user_id != user_id:
        raise HTTPException(status_code=404, detail="Sincronización no encontrada.")
    if sync.status == SyncStatus.completed:
        raise HTTPException(status_code=409, detail="Esta sincronización ya fue confirmada.")

    selections = [s.model_dump() for s in body.selections]
    return await sync_service.confirm_playlist_sync(
        db, sync, access_token, selections, body.playlist_id, body.playlist_name
    )


@router.get("/history", response_model=list[SyncOut])
def history(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    return db.scalars(
        select(Sync)
        .where(Sync.user_id == user_id)
        .options(selectinload(Sync.items))
        .order_by(Sync.created_at.desc())
    ).all()


@router.get("/{sync_id}", response_model=SyncOut)
def detail(sync_id: int, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    sync = db.scalar(
        select(Sync).where(Sync.id == sync_id, Sync.user_id == user_id).options(selectinload(Sync.items))
    )
    if not sync:
        raise HTTPException(status_code=404, detail="Sincronización no encontrada.")
    return sync
