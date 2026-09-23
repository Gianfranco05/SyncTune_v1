"""Regression coverage for playlist_service's return shapes — these feed
directly into Pydantic `response_model`s (schemas/playlist.py), so a shape
mismatch here is a runtime 500 on real data, not just a type nit.
"""

import pytest

from app.schemas.playlist import PlaylistHealthResponse
from app.services import playlist_service, spotify_service

pytestmark = pytest.mark.anyio


def _track(id_: str, name: str, artists: str) -> dict:
    return {
        "id": id_,
        "uri": f"spotify:track:{id_}",
        "name": name,
        "artists": artists,
        "album": "Some Album",
        "album_image": None,
        "external_url": f"https://open.spotify.com/track/{id_}",
        "duration_ms": 200_000,
    }


def _async_return(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner


class TestGetPlaylistHealth:
    async def test_duplicate_groups_are_wrapped_for_the_response_schema(self, monkeypatch):
        # Two tracks that are "the same song" (spec §16) — this is the case
        # the endpoint exists to surface, so it must not crash on it.
        dup_a = _track("1", "Blinding Lights", "The Weeknd")
        dup_b = _track("2", "Blinding Lights", "The Weeknd")
        unique = _track("3", "Starboy", "The Weeknd")

        monkeypatch.setattr(spotify_service, "get_playlist", _async_return({"id": "p1", "name": "My Playlist"}))
        monkeypatch.setattr(spotify_service, "get_playlist_tracks", _async_return([dup_a, unique, dup_b]))

        result = await playlist_service.get_playlist_health("fake-token", "p1")

        assert result["total_tracks"] == 3
        assert result["duplicate_track_count"] == 1
        # Each group must be {"tracks": [...]} — schemas.playlist.DuplicateGroup
        # — not a bare list, or FastAPI's response_model validation fails.
        assert result["duplicate_groups"] == [{"tracks": [dup_a, dup_b]}]
        # The real regression check: this is what FastAPI does with the
        # return value before sending it out. Must not raise.
        PlaylistHealthResponse(**result)

    async def test_no_duplicates_returns_empty_groups(self, monkeypatch):
        monkeypatch.setattr(spotify_service, "get_playlist", _async_return({"id": "p1", "name": "My Playlist"}))
        monkeypatch.setattr(
            spotify_service,
            "get_playlist_tracks",
            _async_return([_track("1", "Song A", "Artist"), _track("2", "Song B", "Artist")]),
        )

        result = await playlist_service.get_playlist_health("fake-token", "p1")

        assert result["duplicate_groups"] == []
        assert result["duplicate_track_count"] == 0
