import pytest

from app.services import youtube_service as yt


class TestExtractVideoId:
    @pytest.mark.parametrize(
        "url,expected_id",
        [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("http://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ?si=abc123", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("  dQw4w9WgXcQ  ", "dQw4w9WgXcQ"),
        ],
    )
    def test_accepts_common_formats(self, url, expected_id):
        assert yt.extract_video_id(url) == expected_id

    @pytest.mark.parametrize(
        "bad_url",
        [
            "https://www.google.com",
            "not a url at all",
            "https://www.youtube.com/watch?list=PL123",  # no v=
            "",
        ],
    )
    def test_rejects_invalid_urls(self, bad_url):
        with pytest.raises(ValueError):
            yt.extract_video_id(bad_url)


class TestExtractPlaylistId:
    @pytest.mark.parametrize(
        "url,expected_id",
        [
            ("https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf", "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"),
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf", "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"),
            ("https://youtube.com/playlist?list=LL", "LL"),
            ("PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf", "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"),
        ],
    )
    def test_accepts_common_formats(self, url, expected_id):
        assert yt.extract_playlist_id(url) == expected_id

    @pytest.mark.parametrize(
        "bad_url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # no list=
            "not a url at all !!",
            "",
        ],
    )
    def test_rejects_invalid_urls(self, bad_url):
        with pytest.raises(ValueError):
            yt.extract_playlist_id(bad_url)


class TestParseDurationMs:
    @pytest.mark.parametrize(
        "iso,expected_ms",
        [
            ("PT3M20S", 200_000),
            ("PT1H2M3S", ((1 * 60 + 2) * 60 + 3) * 1000),
            ("PT45S", 45_000),
            ("PT4M", 240_000),
        ],
    )
    def test_parses_common_durations(self, iso, expected_ms):
        assert yt._parse_duration_ms(iso) == expected_ms


class TestFetchMyPlaylists:
    @pytest.mark.anyio
    async def test_follows_pagination_and_maps_fields(self, monkeypatch):
        import httpx

        real = httpx.AsyncClient

        def handler(request):
            if request.url.params.get("pageToken") == "p2":
                return httpx.Response(200, json={"items": [{"id": "B", "snippet": {"title": "Dos"}}]})
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "A",
                            "snippet": {"title": "Uno", "thumbnails": {"default": {"url": "http://t/1.jpg"}}},
                            "contentDetails": {"itemCount": 7},
                        }
                    ],
                    "nextPageToken": "p2",
                },
            )

        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
        result = await yt.fetch_my_playlists("tok")
        assert result == [
            {"id": "A", "title": "Uno", "video_count": 7, "thumbnail": "http://t/1.jpg"},
            {"id": "B", "title": "Dos", "video_count": None, "thumbnail": None},
        ]

    @pytest.mark.anyio
    async def test_unexpected_shape_raises_external_response_error(self, monkeypatch):
        import httpx
        from app.core.errors import ExternalResponseError

        real = httpx.AsyncClient
        handler = lambda request: httpx.Response(200, json={"items": [{"snippet": {}}]})
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
        with pytest.raises(ExternalResponseError):
            await yt.fetch_my_playlists("tok")
