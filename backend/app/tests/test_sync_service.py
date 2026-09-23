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


class TestAnalyzeYoutubePlaylistBatching:
    """Long playlists are worked through 50 at a time via offset/next_offset."""

    def _patch(self, monkeypatch, total: int):
        from app.services import youtube_service

        monkeypatch.setattr(youtube_service, "extract_playlist_id", lambda url: "PL")
        monkeypatch.setattr(youtube_service, "fetch_playlist_title", _async_return("My Playlist"))
        monkeypatch.setattr(
            youtube_service, "fetch_playlist_video_ids", _async_return([f"v{i}" for i in range(total)])
        )

        async def fake_bulk(video_ids):
            return [
                {"video_id": v, "title": f"T {v}", "channel_title": "c", "duration_ms": 1000} for v in video_ids
            ]

        monkeypatch.setattr(youtube_service, "fetch_videos_bulk", fake_bulk)
        monkeypatch.setattr(sync_service, "_match_candidates", _async_return([]))

    async def test_first_batch_of_a_long_playlist_points_at_the_next(self, monkeypatch):
        self._patch(monkeypatch, total=120)

        result = await sync_service.analyze_youtube_playlist("s", "y", "url")

        assert len(result["items"]) == sync_service.MAX_PLAYLIST_ITEMS
        assert result["offset"] == 0
        assert result["next_offset"] == 50
        assert result["total_video_count"] == 120

    async def test_middle_batch_starts_where_asked(self, monkeypatch):
        self._patch(monkeypatch, total=120)

        result = await sync_service.analyze_youtube_playlist("s", "y", "url", offset=50)

        assert result["items"][0]["video"]["video_id"] == "v50"
        assert result["next_offset"] == 100

    async def test_last_batch_has_no_next_offset(self, monkeypatch):
        self._patch(monkeypatch, total=120)

        result = await sync_service.analyze_youtube_playlist("s", "y", "url", offset=100)

        assert [i["video"]["video_id"] for i in result["items"]] == [f"v{n}" for n in range(100, 120)]
        assert result["next_offset"] is None

    async def test_short_playlist_is_a_single_batch(self, monkeypatch):
        self._patch(monkeypatch, total=10)

        result = await sync_service.analyze_youtube_playlist("s", "y", "url")

        assert len(result["items"]) == 10
        assert result["next_offset"] is None
