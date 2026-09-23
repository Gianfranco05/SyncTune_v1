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
            ("get", "/api/youtube/login", None),
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
