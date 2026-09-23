"""Dashboard numbers — spec §13-14: "No inventar estadísticas. Todo debe
salir de PostgreSQL." Every field here is a direct aggregate over
`syncs`/`sync_items`; nothing is estimated or hardcoded.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Sync, SyncItem, SyncItemStatus, SyncStatus


def get_dashboard_stats(db: Session, user_id: int) -> dict:
    songs_synced = (
        db.scalar(
            select(func.count(SyncItem.id))
            .join(Sync, Sync.id == SyncItem.sync_id)
            .where(Sync.user_id == user_id, SyncItem.status == SyncItemStatus.imported)
        )
        or 0
    )

    duplicates_skipped = (
        db.scalar(
            select(func.count(SyncItem.id))
            .join(Sync, Sync.id == SyncItem.sync_id)
            .where(Sync.user_id == user_id, SyncItem.status == SyncItemStatus.duplicate)
        )
        or 0
    )

    pending_review = (
        db.scalar(select(func.count(Sync.id)).where(Sync.user_id == user_id, Sync.status == SyncStatus.review))
        or 0
    )

    playlists_touched = (
        db.scalar(
            select(func.count(func.distinct(Sync.destination_name))).where(
                Sync.user_id == user_id, Sync.destination_name.is_not(None)
            )
        )
        or 0
    )

    average_confidence = db.scalar(
        select(func.avg(SyncItem.confidence))
        .join(Sync, Sync.id == SyncItem.sync_id)
        .where(Sync.user_id == user_id, SyncItem.confidence.is_not(None))
    )

    last_sync_at = db.scalar(
        select(func.max(Sync.completed_at)).where(Sync.user_id == user_id, Sync.status == SyncStatus.completed)
    )

    return {
        "songs_synced": songs_synced,
        "duplicates_skipped": duplicates_skipped,
        "pending_review": pending_review,
        "playlists_touched": playlists_touched,
        "average_confidence": round(average_confidence, 1) if average_confidence is not None else None,
        "last_sync_at": last_sync_at,
    }


def get_recent_syncs(db: Session, user_id: int, limit: int = 5) -> list[Sync]:
    # `Sync.id.desc()` breaks ties: Postgres's now() returns the same value
    # for every statement within one transaction, so a burst of syncs
    # created together would otherwise sort in an undefined order.
    return db.scalars(
        select(Sync)
        .where(Sync.user_id == user_id)
        .options(selectinload(Sync.items))
        .order_by(Sync.created_at.desc(), Sync.id.desc())
        .limit(limit)
    ).all()
