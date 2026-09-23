from datetime import datetime, timezone

import pytest

from app.models import Sync, SyncItem, SyncItemStatus, SyncStatus, User
from app.services import analytics_service


def _make_user(db) -> User:
    user = User()
    db.add(user)
    db.flush()
    return user


class TestGetDashboardStats:
    def test_counts_are_scoped_to_the_user_and_correct(self, db):
        user = _make_user(db)
        other_user = _make_user(db)

        imported_sync = Sync(
            user_id=user.id,
            source="youtube",
            destination="spotify",
            source_name="Song A",
            destination_name="My Playlist",
            status=SyncStatus.completed,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(imported_sync)
        db.flush()
        db.add(
            SyncItem(
                sync_id=imported_sync.id,
                source_id="yt1",
                source_title="Song A",
                status=SyncItemStatus.imported,
                confidence=95.0,
            )
        )

        duplicate_sync = Sync(
            user_id=user.id,
            source="youtube",
            destination="spotify",
            source_name="Song B",
            destination_name="My Playlist",
            status=SyncStatus.completed,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(duplicate_sync)
        db.flush()
        db.add(
            SyncItem(
                sync_id=duplicate_sync.id,
                source_id="yt2",
                source_title="Song B",
                status=SyncItemStatus.duplicate,
                confidence=80.0,
            )
        )

        pending_sync = Sync(
            user_id=user.id, source="youtube", destination="spotify", source_name="Song C", status=SyncStatus.review
        )
        db.add(pending_sync)
        db.flush()
        db.add(SyncItem(sync_id=pending_sync.id, source_id="yt3", source_title="Song C", status=SyncItemStatus.review))

        # Belongs to a different user — must never leak into these stats.
        other_sync = Sync(
            user_id=other_user.id,
            source="youtube",
            destination="spotify",
            source_name="Not mine",
            destination_name="Other playlist",
            status=SyncStatus.completed,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(other_sync)
        db.flush()
        db.add(
            SyncItem(
                sync_id=other_sync.id,
                source_id="ytX",
                source_title="Not mine",
                status=SyncItemStatus.imported,
                confidence=99.0,
            )
        )
        db.flush()

        stats = analytics_service.get_dashboard_stats(db, user.id)

        assert stats["songs_synced"] == 1
        assert stats["duplicates_skipped"] == 1
        assert stats["pending_review"] == 1
        assert stats["playlists_touched"] == 1
        assert stats["average_confidence"] == pytest.approx(87.5, abs=0.1)
        assert stats["last_sync_at"] is not None

    def test_user_with_no_syncs_has_zeroed_stats(self, db):
        user = _make_user(db)
        db.flush()

        stats = analytics_service.get_dashboard_stats(db, user.id)

        assert stats == {
            "songs_synced": 0,
            "duplicates_skipped": 0,
            "pending_review": 0,
            "playlists_touched": 0,
            "average_confidence": None,
            "last_sync_at": None,
        }


class TestGetRecentSyncs:
    def test_orders_newest_first_and_respects_limit(self, db):
        user = _make_user(db)
        for i in range(3):
            db.add(
                Sync(
                    user_id=user.id,
                    source="youtube",
                    destination="spotify",
                    source_name=f"Song {i}",
                    status=SyncStatus.review,
                )
            )
        db.flush()

        recent = analytics_service.get_recent_syncs(db, user.id, limit=2)

        assert len(recent) == 2
        assert recent[0].source_name == "Song 2"
        assert recent[1].source_name == "Song 1"
