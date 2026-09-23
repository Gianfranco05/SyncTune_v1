import pytest

from app.models import Sync, SyncItem, SyncItemStatus, SyncStatus, User
from app.services import sync_service, spotify_service

pytestmark = pytest.mark.anyio


def _make_user(db) -> User:
    user = User()
    db.add(user)
    db.flush()
    return user


def _make_playlist_sync(db, user_id: int, n_items: int) -> tuple[Sync, list[SyncItem]]:
    sync = Sync(
        user_id=user_id,
        source="youtube",
        destination="spotify",
        source_name="My Playlist",
        status=SyncStatus.review,
    )
    db.add(sync)
    db.flush()

    items = []
    for i in range(n_items):
        item = SyncItem(sync_id=sync.id, source_id=f"yt{i}", source_title=f"Song {i}", status=SyncItemStatus.review)
        db.add(item)
        db.flush()
        items.append(item)

    db.refresh(sync)
    return sync, items


class TestConfirmPlaylistSync:
    async def test_imports_new_skips_requested_and_flags_duplicates(self, db, monkeypatch):
        user = _make_user(db)
        sync, items = _make_playlist_sync(db, user.id, n_items=3)

        # track_dup already exists in the destination playlist.
        monkeypatch.setattr(
            spotify_service, "get_playlist_track_ids", _async_return({"track_dup"})
        )
        added_calls: list[tuple[str, list[str]]] = []

        async def fake_add_tracks(access_token, playlist_id, track_uris):
            added_calls.append((playlist_id, track_uris))

        monkeypatch.setattr(spotify_service, "add_tracks_to_playlist", fake_add_tracks)

        selections = [
            {
                "item_id": items[0].id,
                "track_id": "track_new",
                "track_uri": "spotify:track:track_new",
                "track_name": "Song 0",
                "track_artists": "Artist",
                "confidence": 92.0,
                "skip": False,
            },
            {
                "item_id": items[1].id,
                "track_id": "track_dup",
                "track_uri": "spotify:track:track_dup",
                "track_name": "Song 1",
                "track_artists": "Artist",
                "confidence": 88.0,
                "skip": False,
            },
            {
                "item_id": items[2].id,
                "track_id": None,
                "track_uri": None,
                "track_name": None,
                "track_artists": None,
                "confidence": None,
                "skip": True,
            },
        ]

        result = await sync_service.confirm_playlist_sync(
            db, sync, "fake-token", selections, "playlist-123", "My Playlist"
        )

        assert result.status == SyncStatus.completed
        assert result.completed_at is not None
        assert added_calls == [("playlist-123", ["spotify:track:track_new"])]

        db.refresh(items[0])
        db.refresh(items[1])
        db.refresh(items[2])
        assert items[0].status == SyncItemStatus.imported
        assert items[1].status == SyncItemStatus.duplicate
        assert items[2].status == SyncItemStatus.skipped

    async def test_does_not_call_spotify_when_nothing_to_add(self, db, monkeypatch):
        user = _make_user(db)
        sync, items = _make_playlist_sync(db, user.id, n_items=1)

        monkeypatch.setattr(spotify_service, "get_playlist_track_ids", _async_return(set()))

        called = False

        async def fake_add_tracks(*args, **kwargs):
            nonlocal called
            called = True

        monkeypatch.setattr(spotify_service, "add_tracks_to_playlist", fake_add_tracks)

        selections = [{"item_id": items[0].id, "skip": True}]

        await sync_service.confirm_playlist_sync(db, sync, "fake-token", selections, "playlist-123", "My Playlist")

        assert called is False


def _async_return(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner
