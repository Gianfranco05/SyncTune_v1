"""All communication with the Spotify Web API goes through this module.

Endpoint paths here reflect the February/March 2026 Spotify Web API
migration for Development Mode apps (see IMPLEMENTATION_PLAN.md, FASE 0):
playlist track endpoints moved from `/tracks` to `/items`, and playlist
creation moved from `/users/{user_id}/playlists` to `/me/playlists`.

Response parsing is defensive on purpose: a 2xx with an unexpected shape
raises ExternalResponseError (a friendly 502) instead of a bare KeyError.
"""

from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.errors import ExternalResponseError

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"

SCOPES = "playlist-read-private playlist-modify-private playlist-modify-public"

# Development Mode capped /search's `limit` at 10 (previously 50) as of the
# Feb 2026 migration.
_MAX_SEARCH_LIMIT = 10

# Hard stop for "follow `next` until done" loops, so a misbehaving API can
# never spin us forever (100 pages x 50-100 items is far past any real use).
_MAX_PAGES = 100


def build_auth_url(state: str) -> str:
    params = {
        "client_id": settings.spotify_client_id,
        "response_type": "code",
        "redirect_uri": settings.spotify_redirect_uri,
        "scope": SCOPES,
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.spotify_redirect_uri,
            },
            auth=(settings.spotify_client_id, settings.spotify_client_secret),
        )
    response.raise_for_status()
    return response.json()


async def refresh_access_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            auth=(settings.spotify_client_id, settings.spotify_client_secret),
        )
    response.raise_for_status()
    return response.json()


def _parse_track(t: dict) -> dict:
    try:
        images = t["album"].get("images") or []
        return {
            "id": t["id"],
            "uri": t["uri"],
            "name": t["name"],
            "artists": ", ".join(a["name"] for a in t["artists"]),
            "album": t["album"]["name"],
            "album_image": images[0]["url"] if images else None,
            "external_url": t["external_urls"]["spotify"],
            "duration_ms": t["duration_ms"],
        }
    except (KeyError, TypeError, AttributeError, IndexError) as e:
        raise ExternalResponseError(f"Unexpected Spotify track shape: {e!r}") from e


def _entry_track(entry: dict) -> dict | None:
    """The track inside a playlist entry, or None for things to skip.

    The Feb 2026 migration renamed several playlist fields (`tracks` ->
    `items`), and the per-entry key may have moved from `track` to `item`
    with it — accept either rather than betting on one. Local files,
    removed tracks and podcast episodes have no usable Spotify track id.
    """
    if not isinstance(entry, dict):
        raise ExternalResponseError("Unexpected playlist entry shape")
    t = entry.get("track") or entry.get("item")
    if not isinstance(t, dict) or not t.get("id"):
        return None
    if t.get("type", "track") != "track":
        return None
    return t


async def _get_all_items(client: httpx.AsyncClient, url: str, params: dict, access_token: str) -> list[dict]:
    """Follows Spotify's `next` links and returns every entry of `items`."""
    headers = {"Authorization": f"Bearer {access_token}"}
    entries: list[dict] = []
    next_url: str | None = url
    next_params: dict | None = params
    for _ in range(_MAX_PAGES):
        if not next_url:
            break
        response = await client.get(next_url, params=next_params, headers=headers)
        response.raise_for_status()
        data = response.json()
        page = data.get("items") if isinstance(data, dict) else None
        if not isinstance(page, list):
            raise ExternalResponseError("Unexpected Spotify paging shape: missing 'items' list")
        entries.extend(page)
        next_url = data.get("next")
        next_params = None  # `next` is a full URL with its own query string
    return entries


async def search_tracks(access_token: str, query: str, limit: int = 5) -> list[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/search",
            params={"q": query, "type": "track", "limit": min(limit, _MAX_SEARCH_LIMIT)},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    response.raise_for_status()
    try:
        items = response.json()["tracks"]["items"]
    except (KeyError, TypeError) as e:
        raise ExternalResponseError(f"Unexpected Spotify search shape: {e!r}") from e
    return [_parse_track(t) for t in items if isinstance(t, dict) and t.get("id")]


async def get_current_user(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or "id" not in data:
        raise ExternalResponseError("Unexpected Spotify /me shape: missing 'id'")
    return data


async def get_user_playlists(access_token: str) -> list[dict]:
    """Every playlist of the user (follows pagination — used to be capped
    at the first 50)."""
    async with httpx.AsyncClient() as client:
        entries = await _get_all_items(client, f"{API_BASE}/me/playlists", {"limit": 50}, access_token)
    playlists = []
    for p in entries:
        try:
            playlists.append({"id": p["id"], "name": p["name"]})
        except (KeyError, TypeError) as e:
            raise ExternalResponseError(f"Unexpected Spotify playlist shape: {e!r}") from e
    return playlists


async def create_playlist(access_token: str, name: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE}/me/playlists",
            json={"name": name, "public": False},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    response.raise_for_status()
    data = response.json()
    try:
        return {"id": data["id"], "name": data["name"]}
    except (KeyError, TypeError) as e:
        raise ExternalResponseError(f"Unexpected Spotify create-playlist shape: {e!r}") from e


async def get_playlist(access_token: str, playlist_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/playlists/{playlist_id}",
            params={"fields": "id,name"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    response.raise_for_status()
    data = response.json()
    try:
        return {"id": data["id"], "name": data["name"]}
    except (KeyError, TypeError) as e:
        raise ExternalResponseError(f"Unexpected Spotify playlist shape: {e!r}") from e


async def get_playlist_tracks(access_token: str, playlist_id: str) -> list[dict]:
    """Full track details for every item in a playlist — spec §15-19:
    playlist comparator, duplicate detection, merge."""
    params = {"fields": "items(track,item),next", "limit": 100}
    async with httpx.AsyncClient() as client:
        entries = await _get_all_items(client, f"{API_BASE}/playlists/{playlist_id}/items", params, access_token)
    tracks = []
    for entry in entries:
        t = _entry_track(entry)
        if t is not None:
            tracks.append(_parse_track(t))
    return tracks


async def add_tracks_to_playlist(access_token: str, playlist_id: str, track_uris: list[str]) -> None:
    """Batches in groups of 100 — the max `uris` accepts per call."""
    async with httpx.AsyncClient() as client:
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i : i + 100]
            response = await client.post(
                f"{API_BASE}/playlists/{playlist_id}/items",
                json={"uris": batch},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()


async def add_track_to_playlist(access_token: str, playlist_id: str, track_uri: str) -> None:
    await add_tracks_to_playlist(access_token, playlist_id, [track_uri])


async def get_playlist_track_ids(access_token: str, playlist_id: str) -> set[str]:
    """All track ids already in a playlist, for duplicate detection (spec §20)."""
    params = {"fields": "items(track(id),item(id)),next", "limit": 100}
    async with httpx.AsyncClient() as client:
        entries = await _get_all_items(client, f"{API_BASE}/playlists/{playlist_id}/items", params, access_token)
    ids: set[str] = set()
    for entry in entries:
        t = _entry_track(entry)
        if t is not None:
            ids.add(t["id"])
    return ids
