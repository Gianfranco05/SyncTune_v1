from datetime import datetime

from pydantic import BaseModel

from app.schemas.sync import SyncOut


class DashboardStats(BaseModel):
    songs_synced: int
    duplicates_skipped: int
    pending_review: int
    playlists_touched: int
    average_confidence: float | None
    last_sync_at: datetime | None


class DashboardResponse(BaseModel):
    stats: DashboardStats
    recent: list[SyncOut]
