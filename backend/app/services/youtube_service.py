import re
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from app.core.config import settings
from app.core.errors import ExternalResponseError

YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
YOUTUBE_PLAYLISTS_URL = "https://www.googleapis.com/youtube/v3/playlists"
YOUTUBE_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"

# Google OAuth 2.0 (spec §5, FASE 5). `youtube.readonly` is the minimum
# scope for reading playlists — see docs/EVOLUTION_PLAN.md §3 for why we
# didn't request the broader `youtube` scope or an `openid`/`profile`
# scope (channels.list?mine=true gives us an identity without them).
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"

_VIDEO_ID_RE = re.compile(r"^[\w-]{11}$")

_ISO8601_DURATION_RE = re.compile(
    r"P(?:\d+D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
)


class VideoNotFoundError(Exception):
    pass


class PlaylistNotFoundError(Exception):
    pass


class ChannelNotFoundError(Exception):
    """The Google account has no YouTube channel to connect."""


class GoogleOAuthNotConfiguredError(Exception):
    """GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI missing from .env — FASE 5 is
    opt-in, so the app must still run fine without them configured."""


def _require_google_oauth_configured() -> None:
    if not (settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri):
        raise GoogleOAuthNotConfiguredError(
            "Conectar YouTube no está disponible: faltan GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET/"
            "GOOGLE_REDIRECT_URI en el .env del backend."
        )


def _parse_duration_ms(iso8601_duration: str) -> int | None:
    match = _ISO8601_DURATION_RE.match(iso8601_duration)
    if not match:
        return None
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return ((hours * 60 + minutes) * 60 + seconds) * 1000


def extract_video_id(url_or_id: str) -> str:
    candidate = url_or_id.strip()
    if _VIDEO_ID_RE.match(candidate):
        return candidate

    parsed = urlparse(candidate)
    if parsed.hostname in ("youtu.be",):
        video_id = parsed.path.lstrip("/")
        if _VIDEO_ID_RE.match(video_id):
            return video_id
    if parsed.hostname and "youtube.com" in parsed.hostname:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
            if video_id and _VIDEO_ID_RE.match(video_id):
                return video_id
        shorts_match = re.match(r"^/shorts/([\w-]{11})", parsed.path)
        if shorts_match:
            return shorts_match.group(1)

    raise ValueError(f"No se pudo extraer un video id de: {url_or_id}")


def extract_playlist_id(url_or_id: str) -> str:
    """Accepts a bare playlist ID, a `/playlist?list=...` URL, or a
    `/watch?v=...&list=...` URL (a video played from within a playlist)."""
    candidate = url_or_id.strip()

    parsed = urlparse(candidate)
    if parsed.query:
        list_id = parse_qs(parsed.query).get("list", [None])[0]
        if list_id:
            return list_id

    if not parsed.scheme and re.match(r"^[\w-]{2,64}$", candidate):
        return candidate

    raise ValueError(f"No se pudo extraer un playlist id de: {url_or_id}")


def _parse_video(item: dict) -> dict:
    try:
        return {
            "video_id": item["id"],
            "title": item["snippet"]["title"],
            "channel_title": item["snippet"]["channelTitle"],
            "duration_ms": _parse_duration_ms(item["contentDetails"]["duration"]),
        }
    except (KeyError, TypeError) as e:
        raise ExternalResponseError(f"Unexpected YouTube video shape: {e!r}") from e


async def fetch_video_title(video_id: str) -> dict:
    # part="snippet,contentDetails" costs the same 1 quota unit as
    # "snippet" alone — contentDetails.duration feeds the matching engine's
    # duration score (see matching_service.score_candidate).
    async with httpx.AsyncClient() as client:
        response = await client.get(
            YOUTUBE_VIDEOS_URL,
            params={
                "part": "snippet,contentDetails",
                "id": video_id,
                "key": settings.youtube_api_key,
            },
        )
    response.raise_for_status()
    data = response.json()
    items = data.get("items", [])
    if not items:
        raise VideoNotFoundError(f"Video no encontrado: {video_id}")

    parsed = _parse_video(items[0])
    parsed["video_id"] = video_id
    return parsed


async def fetch_playlist_title(playlist_id: str, access_token: str) -> str:
    """Uses the user's OAuth token (not the API key) so it works for
    private playlists too — that's the whole point of connecting YouTube."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            YOUTUBE_PLAYLISTS_URL,
            params={"part": "snippet", "id": playlist_id},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    response.raise_for_status()
    items = response.json().get("items", [])
    if not items:
        raise PlaylistNotFoundError(f"Playlist no encontrada: {playlist_id}")
    try:
        return items[0]["snippet"]["title"]
    except (KeyError, TypeError) as e:
        raise ExternalResponseError(f"Unexpected YouTube playlist shape: {e!r}") from e


_MAX_MY_PLAYLIST_PAGES = 10


async def fetch_my_playlists(access_token: str) -> list[dict]:
    """The connected account's own playlists (`mine=true`), so the UI can
    offer them as a pick-list instead of making the user paste a URL.
    Needs the user's OAuth token — the API key can't see an account's
    playlists. 1 quota unit per page of 50."""
    playlists: list[dict] = []
    params: dict = {"part": "snippet,contentDetails", "mine": "true", "maxResults": 50}
    async with httpx.AsyncClient() as client:
        for _ in range(_MAX_MY_PLAYLIST_PAGES):
            response = await client.get(
                YOUTUBE_PLAYLISTS_URL, params=params, headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            data = response.json()
            for item in data.get("items", []):
                try:
                    thumbnails = item["snippet"].get("thumbnails") or {}
                    thumb = thumbnails.get("default") or thumbnails.get("medium") or {}
                    playlists.append(
                        {
                            "id": item["id"],
                            "title": item["snippet"]["title"],
                            "video_count": (item.get("contentDetails") or {}).get("itemCount"),
                            "thumbnail": thumb.get("url"),
                        }
                    )
                except (KeyError, TypeError, AttributeError) as e:
                    raise ExternalResponseError(f"Unexpected YouTube playlist shape: {e!r}") from e
            next_token = data.get("nextPageToken")
            if not next_token:
                break
            params = {**params, "pageToken": next_token}
    return playlists


async def fetch_playlist_video_ids(playlist_id: str, access_token: str, max_items: int = 200) -> list[str]:
    """`part=contentDetails` only — 1 quota unit per page of 50, and we
    don't need snippet/status here: fetch_videos_bulk (API key, videos.list)
    naturally drops any id that comes back deleted/private, so we don't
    need to pre-filter by status."""
    video_ids: list[str] = []
    params: dict = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": 50}
    async with httpx.AsyncClient() as client:
        while len(video_ids) < max_items:
            response = await client.get(
                YOUTUBE_PLAYLIST_ITEMS_URL, params=params, headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            data = response.json()
            for item in data.get("items", []):
                try:
                    video_ids.append(item["contentDetails"]["videoId"])
                except (KeyError, TypeError) as e:
                    raise ExternalResponseError(f"Unexpected YouTube playlist item shape: {e!r}") from e
            next_token = data.get("nextPageToken")
            if not next_token:
                break
            params = {**params, "pageToken": next_token}
    return video_ids[:max_items]


async def fetch_videos_bulk(video_ids: list[str]) -> list[dict]:
    """Batched videos.list, up to 50 ids per call (spec §8: minimize
    YouTube quota — 1 unit per call regardless of batch size, same as a
    single video). Deleted/private video ids are silently absent from the
    response; callers should treat a missing id as "not found"."""
    results: list[dict] = []
    async with httpx.AsyncClient() as client:
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            response = await client.get(
                YOUTUBE_VIDEOS_URL,
                params={"part": "snippet,contentDetails", "id": ",".join(batch), "key": settings.youtube_api_key},
            )
            response.raise_for_status()
            for item in response.json().get("items", []):
                results.append(_parse_video(item))
    return results


def build_auth_url(state: str) -> str:
    _require_google_oauth_configured()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": YOUTUBE_READONLY_SCOPE,
        "access_type": "offline",
        # Forces Google to re-issue a refresh_token every time (it's only
        # issued on the user's *first* consent otherwise), since a Testing
        # (unverified) app's refresh tokens expire after 7 days — see
        # docs/EVOLUTION_PLAN.md §3 — and we'd rather always get a fresh one
        # than have a reconnect silently fail to renew it.
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict:
    _require_google_oauth_configured()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    response.raise_for_status()
    return response.json()


async def refresh_access_token(refresh_token: str) -> dict:
    _require_google_oauth_configured()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "refresh_token",
            },
        )
    response.raise_for_status()
    return response.json()


async def get_current_user(access_token: str) -> dict:
    """Identifies the connected Google account by its YouTube channel —
    avoids requesting an extra `openid`/`profile` scope just for a name."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            YOUTUBE_CHANNELS_URL,
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    response.raise_for_status()
    items = response.json().get("items", [])
    if not items:
        raise ChannelNotFoundError("Esta cuenta de Google no tiene un canal de YouTube.")

    channel = items[0]
    return {"id": channel["id"], "display_name": channel["snippet"]["title"]}
