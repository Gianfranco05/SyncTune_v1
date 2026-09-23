import pytest

from app.services import youtube_service as yt


class TestBuildAuthUrl:
    def test_raises_when_not_configured(self, monkeypatch):
        monkeypatch.setattr(yt.settings, "google_client_id", None)
        monkeypatch.setattr(yt.settings, "google_client_secret", None)
        monkeypatch.setattr(yt.settings, "google_redirect_uri", None)
        with pytest.raises(yt.GoogleOAuthNotConfiguredError):
            yt.build_auth_url("some-state")

    def test_builds_url_with_readonly_scope_and_offline_access(self, monkeypatch):
        monkeypatch.setattr(yt.settings, "google_client_id", "client-123")
        monkeypatch.setattr(yt.settings, "google_client_secret", "secret-456")
        monkeypatch.setattr(yt.settings, "google_redirect_uri", "http://127.0.0.1:8000/api/youtube/callback")

        url = yt.build_auth_url("some-state")

        assert url.startswith(yt.GOOGLE_AUTH_URL)
        assert "client_id=client-123" in url
        assert "state=some-state" in url
        assert "access_type=offline" in url
        assert "prompt=consent" in url
        # Only the minimum scope needed to read playlists (spec §5) — never
        # the broader "youtube" (modify) scope.
        assert "youtube.readonly" in url
        assert "scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fyoutube%2Ffull" not in url
