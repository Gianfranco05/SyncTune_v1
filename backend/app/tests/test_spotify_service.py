"""spotify_service against a fake Spotify (httpx.MockTransport): pagination,
tolerance for the renamed playlist-entry key, and clean failures on shapes
we don't recognize."""

import httpx
import pytest

from app.core.errors import ExternalResponseError
from app.services import spotify_service

pytestmark = pytest.mark.anyio

_RealAsyncClient = httpx.AsyncClient


def _fake_spotify(monkeypatch, handler):
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: _RealAsyncClient(transport=httpx.MockTransport(handler), **kwargs),
    )


def _raw_track(id_: str, name: str = "Song", artist: str = "Artist", **extra) -> dict:
    return {
        "id": id_,
        "uri": f"spotify:track:{id_}",
        "name": name,
        "type": "track",
        "artists": [{"name": artist}],
        "album": {"name": "Album", "images": [{"url": "http://img"}]},
        "external_urls": {"spotify": f"https://open.spotify.com/track/{id_}"},
        "duration_ms": 200_000,
        **extra,
    }


class TestGetUserPlaylistsPagination:
    async def test_follows_next_links_past_the_first_page(self, monkeypatch):
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if "offset=50" in str(request.url):
                return httpx.Response(200, json={"items": [{"id": "p3", "name": "Third"}], "next": None})
            return httpx.Response(
                200,
                json={
                    "items": [{"id": "p1", "name": "First"}, {"id": "p2", "name": "Second"}],
                    "next": "https://api.spotify.com/v1/me/playlists?offset=50&limit=50",
                },
            )

        _fake_spotify(monkeypatch, handler)

        playlists = await spotify_service.get_user_playlists("token")

        assert [p["id"] for p in playlists] == ["p1", "p2", "p3"]
        assert len(calls) == 2

    async def test_missing_items_list_is_a_clean_error(self, monkeypatch):
        _fake_spotify(monkeypatch, lambda request: httpx.Response(200, json={"unexpected": True}))

        with pytest.raises(ExternalResponseError):
            await spotify_service.get_user_playlists("token")


class TestPlaylistEntries:
    async def test_accepts_both_track_and_item_keys_and_skips_unusable_entries(self, monkeypatch):
        entries = [
            {"track": _raw_track("a")},  # classic shape
            {"item": _raw_track("b")},  # possible post-migration shape
            {"track": None},  # removed track
            {"track": {"id": None, "name": "Local file"}},  # local file, no id
            {"track": _raw_track("ep", type="episode")},  # podcast episode
        ]
        _fake_spotify(monkeypatch, lambda request: httpx.Response(200, json={"items": entries, "next": None}))

        tracks = await spotify_service.get_playlist_tracks("token", "pl")
        ids = await spotify_service.get_playlist_track_ids("token", "pl")

        assert [t["id"] for t in tracks] == ["a", "b"]
        assert ids == {"a", "b"}

    async def test_track_missing_a_required_field_is_a_clean_error(self, monkeypatch):
        broken = _raw_track("a")
        del broken["duration_ms"]
        _fake_spotify(monkeypatch, lambda request: httpx.Response(200, json={"items": [{"track": broken}], "next": None}))

        with pytest.raises(ExternalResponseError):
            await spotify_service.get_playlist_tracks("token", "pl")


class TestSearchTracks:
    async def test_parses_results(self, monkeypatch):
        _fake_spotify(
            monkeypatch,
            lambda request: httpx.Response(200, json={"tracks": {"items": [_raw_track("a", "Blinding Lights", "The Weeknd")]}}),
        )

        results = await spotify_service.search_tracks("token", "blinding lights")

        assert results[0]["name"] == "Blinding Lights"
        assert results[0]["artists"] == "The Weeknd"

    async def test_unexpected_shape_is_a_clean_error(self, monkeypatch):
        _fake_spotify(monkeypatch, lambda request: httpx.Response(200, json={"nope": 1}))

        with pytest.raises(ExternalResponseError):
            await spotify_service.search_tracks("token", "x")
