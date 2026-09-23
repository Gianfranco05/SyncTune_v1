"""All communication with the Spotify Web API goes through this module.

Endpoint paths here reflect the February/March 2026 Spotify Web API
migration for Development Mode apps (see IMPLEMENTATION_PLAN.md, FASE 0):
playlist track endpoints moved from `/tracks` to `/items`, and playlist
creation moved from `/users/{user_id}/playlists` to `/me/playlists`.
"""

from urllib.parse import urlencode

import httpx

from app.core.config import settings

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"

SCOPES = "playlist-read-private playlist-modify-private playlist-modify-public"

# Development Mode capped /search's `limit` at 10 (previously 50) as of the
# Feb 2026 migration.
_MAX_SEARCH_LIMIT = 10


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


async def search_tracks(access_token: str, query: str, limit: int = 5) -> list[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/search",
            params={"q": query, "type": "track", "limit": min(limit, _MAX_SEARCH_LIMIT)},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    response.raise_for_status()
    items = response.json()["tracks"]["items"]
    return [
        {
            "id": t["id"],
            "uri": t["uri"],
            "name": t["name"],
            "artists": ", ".join(a["name"] for a in t["artists"]),
            "album": t["album"]["name"],
            "album_image": t["album"]["images"][0]["url"] if t["album"]["images"] else None,
            "external_url": t["external_urls"]["spotify"],
            "duration_ms": t["duration_ms"],
        }
        for t in items
    ]


async def get_current_user(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    response.raise_for_status()
    return response.json()


async def get_user_playlists(access_token: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/me/playlists",
            params={"limit": 50},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    response.raise_for_status()
    items = response.json()["items"]
    return [{"id": p["id"], "name": p["name"]} for p in items]


async def create_playlist(access_token: str, name: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE}/me/playlists",
            json={"name": name, "public": False},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    response.raise_for_status()
    data = response.json()
    return {"id": data["id"], "name": data["name"]}


async def get_playlist(access_token: str, playlist_id: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/playlists/{playlist_id}",
            params={"fields": "id,name"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    response.raise_for_status()
    data = response.json()
    return {"id": data["id"], "name": data["name"]}


async def get_playlist_tracks(access_token: str, playlist_id: str) -> list[dict]:
    """Full track details for every item in a playlist — spec §15-19:
    playlist comparator, duplicate detection, merge."""
    tracks: list[dict] = []
    url = f"{API_BASE}/playlists/{playlist_id}/items"
    params: dict | None = {
        "fields": "items(track(id,uri,name,artists,album,duration_ms,external_urls)),next",
        "limit": 100,
    }
    async with httpx.AsyncClient() as client:
        while url:
            response = await client.get(url, params=params, headers={"Authorization": f"Bearer {access_token}"})
            response.raise_for_status()
            data = response.json()
            for item in data.get("items", []):
                t = item.get("track")
                if not t or not t.get("id"):
                    continue
                tracks.append(
                    {
                        "id": t["id"],
                        "uri": t["uri"],
                        "name": t["name"],
                        "artists": ", ".join(a["name"] for a in t["artists"]),
                        "album": t["album"]["name"],
                        "album_image": t["album"]["images"][0]["url"] if t["album"]["images"] else None,
                        "external_url": t["external_urls"]["spotify"],
                        "duration_ms": t["duration_ms"],
                    }
                )
            url = data.get("next")
            params = None
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
    ids: set[str] = set()
    url = f"{API_BASE}/playlists/{playlist_id}/items"
    params: dict | None = {"fields": "items(track(id)),next", "limit": 100}
    async with httpx.AsyncClient() as client:
        while url:
            response = await client.get(url, params=params, headers={"Authorization": f"Bearer {access_token}"})
            response.raise_for_status()
            data = response.json()
            for item in data.get("items", []):
                track = item.get("track")
                if track and track.get("id"):
                    ids.add(track["id"])
            url = data.get("next")
            params = None  # `next` is already a full URL with its own query string
    return ids
