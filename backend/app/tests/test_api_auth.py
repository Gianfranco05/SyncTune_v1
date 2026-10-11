"""spec §58 (ownership) + §61 (seguridad): every endpoint that touches a
user's data or an external token must reject an unauthenticated request.
This is a blunt but valuable check — nothing here should ever leak past a
missing session.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestUnauthenticatedAccessIsRejected:
    @pytest.mark.parametrize(
        "method,path,json_body",
        [
            ("get", "/api/spotify/playlists", None),
            ("post", "/api/spotify/playlists", {"name": "x"}),
            ("post", "/api/spotify/playlists/some-id/tracks", {"track_uri": "spotify:track:x"}),
            ("get", "/api/spotify/search?q=abc", None),
            ("get", "/api/youtube/login", None),
            ("get", "/api/youtube/playlists", None),
            ("post", "/api/sync/preview", {"youtube_url": "https://youtube.com/watch?v=x"}),
            ("post", "/api/sync/1/confirm", {"track_id": "x", "track_uri": "x", "track_name": "x", "track_artists": "x", "playlist_id": "x", "playlist_name": "x"}),
            ("get", "/api/sync/history", None),
            ("get", "/api/sync/1", None),
            (
                "post",
                "/api/sync/playlist/preview",
                {"youtube_url": "https://youtube.com/playlist?list=x"},
            ),
            (
                "post",
                "/api/sync/1/playlist/confirm",
                {"playlist_id": "x", "playlist_name": "x", "selections": []},
            ),
            ("get", "/api/dashboard", None),
            ("get", "/api/playlists/compare?playlist_a_id=a&playlist_b_id=b", None),
            ("get", "/api/playlists/some-id/health", None),
            ("post", "/api/playlists/merge/preview", {"source_playlist_ids": ["a", "b"]}),
            (
                "post",
                "/api/playlists/merge/confirm",
                {"source_playlist_ids": ["a", "b"], "new_playlist_name": "x"},
            ),
        ],
    )
    def test_returns_401_without_a_session(self, method, path, json_body):
        response = client.request(method, path, json=json_body)
        assert response.status_code == 401, f"{method.upper()} {path} returned {response.status_code}, expected 401"
        assert "detail" in response.json()


class TestDisconnectIsIdempotentWithoutASession:
    """Intentionally NOT 401: disconnecting when there was never a
    connection is a harmless no-op (idempotent, like DELETE), not an
    ownership violation — nothing is read or changed."""

    @pytest.mark.parametrize("path", ["/api/spotify/disconnect", "/api/youtube/disconnect"])
    def test_returns_ok_without_a_session(self, path):
        response = client.post(path)
        assert response.status_code == 200
        assert response.json() == {"ok": True}


class TestExternalFailuresAreFriendly:
    """Spotify/YouTube going wrong must surface as a plain 502 message,
    never a raw 500 or an HTTP code (spec §41)."""

    def test_unexpected_response_shape_maps_to_a_friendly_502(self, monkeypatch):
        from app.core.errors import ExternalResponseError
        from app.services import spotify_service

        async def boom(*args, **kwargs):
            raise ExternalResponseError("shape changed")

        # Auth is exercised elsewhere; bypass it to reach the handler.
        from app.core.security import get_valid_access_token

        app.dependency_overrides[get_valid_access_token] = lambda: "token"
        monkeypatch.setattr(spotify_service, "get_user_playlists", boom)
        try:
            response = client.get("/api/spotify/playlists")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 502
        assert "no esperábamos" in response.json()["detail"]
