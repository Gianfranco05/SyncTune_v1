from datetime import datetime

from pydantic import BaseModel, Field

from app.models import SyncItemStatus, SyncStatus
from app.schemas.spotify import SpotifyTrackCandidate
from app.schemas.youtube import YoutubeVideo


class SyncPreviewRequest(BaseModel):
    youtube_url: str


class SyncPreviewResponse(BaseModel):
    sync_id: int
    video: YoutubeVideo
    candidates: list[SpotifyTrackCandidate]


class SyncConfirmRequest(BaseModel):
    track_id: str
    track_uri: str
    track_name: str
    track_artists: str
    confidence: float | None = None
    playlist_id: str
    playlist_name: str


class SyncItemOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    source_title: str
    source_artist: str | None
    destination_title: str | None
    destination_artist: str | None
    status: SyncItemStatus
    confidence: float | None


class SyncOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    source: str
    destination: str
    source_name: str
    destination_name: str | None
    status: SyncStatus
    created_at: datetime
    completed_at: datetime | None
    items: list[SyncItemOut] = []


class PlaylistPreviewRequest(BaseModel):
    youtube_url: str
    # Start of the batch, for playlists longer than one batch (see
    # sync_service.MAX_PLAYLIST_ITEMS).
    offset: int = Field(default=0, ge=0)


class PlaylistPreviewItem(BaseModel):
    item_id: int
    video: YoutubeVideo
    candidates: list[SpotifyTrackCandidate]


class PlaylistPreviewResponse(BaseModel):
    sync_id: int
    playlist_title: str
    total_video_count: int
    offset: int
    next_offset: int | None
    items: list[PlaylistPreviewItem]


class PlaylistSelection(BaseModel):
    item_id: int
    track_id: str | None = None
    track_uri: str | None = None
    track_name: str | None = None
    track_artists: str | None = None
    confidence: float | None = None
    skip: bool = False


class PlaylistConfirmRequest(BaseModel):
    playlist_id: str
    playlist_name: str
    selections: list[PlaylistSelection]
