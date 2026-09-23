from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_valid_access_token
from app.schemas.playlist import (
    MergeConfirmRequest,
    MergeConfirmResponse,
    MergePreviewRequest,
    MergePreviewResponse,
    PlaylistCompareResponse,
    PlaylistHealthResponse,
)
from app.services import playlist_service

router = APIRouter(prefix="/api/playlists", tags=["playlists"])


@router.get("/compare", response_model=PlaylistCompareResponse)
async def compare(
    playlist_a_id: str,
    playlist_b_id: str,
    access_token: str = Depends(get_valid_access_token),
):
    return await playlist_service.compare_playlists(access_token, playlist_a_id, playlist_b_id)


@router.get("/{playlist_id}/health", response_model=PlaylistHealthResponse)
async def health(playlist_id: str, access_token: str = Depends(get_valid_access_token)):
    return await playlist_service.get_playlist_health(access_token, playlist_id)


@router.post("/merge/preview", response_model=MergePreviewResponse)
async def merge_preview(body: MergePreviewRequest, access_token: str = Depends(get_valid_access_token)):
    if len(body.source_playlist_ids) < 2:
        raise HTTPException(status_code=400, detail="Elegí al menos 2 playlists para fusionar.")
    return await playlist_service.merge_preview(access_token, body.source_playlist_ids, body.dedupe)


@router.post("/merge/confirm", response_model=MergeConfirmResponse)
async def merge_confirm(body: MergeConfirmRequest, access_token: str = Depends(get_valid_access_token)):
    if len(body.source_playlist_ids) < 2:
        raise HTTPException(status_code=400, detail="Elegí al menos 2 playlists para fusionar.")
    if not body.destination_playlist_id and not body.new_playlist_name:
        raise HTTPException(status_code=400, detail="Indicá una playlist destino o un nombre para la nueva playlist.")
    return await playlist_service.merge_confirm(
        access_token,
        body.source_playlist_ids,
        body.dedupe,
        body.destination_playlist_id,
        body.new_playlist_name,
    )
