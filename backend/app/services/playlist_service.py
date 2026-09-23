"""Read-then-act operations across Spotify playlists — comparator (spec
§15-16), duplicate detection / "Playlist Health" (§18-19) and merge (§17).

Unlike the YouTube->Spotify sync flow, these operations are Spotify-to-
Spotify and don't fit the `Sync`/`SyncItem` model (built around a YouTube
source item) — kept stateless on purpose rather than stretching that
schema (Regla: elegir la solución más simple).
"""

import asyncio

from app.services import spotify_service, track_identity_service


async def compare_playlists(access_token: str, playlist_a_id: str, playlist_b_id: str) -> dict:
    playlist_a, playlist_b = await asyncio.gather(
        spotify_service.get_playlist(access_token, playlist_a_id),
        spotify_service.get_playlist(access_token, playlist_b_id),
    )
    tracks_a, tracks_b = await asyncio.gather(
        spotify_service.get_playlist_tracks(access_token, playlist_a_id),
        spotify_service.get_playlist_tracks(access_token, playlist_b_id),
    )
    result = track_identity_service.compare_track_lists(tracks_a, tracks_b)
    return {
        "playlist_a_name": playlist_a["name"],
        "playlist_b_name": playlist_b["name"],
        **result,
    }


async def get_playlist_health(access_token: str, playlist_id: str) -> dict:
    playlist, tracks = await asyncio.gather(
        spotify_service.get_playlist(access_token, playlist_id),
        spotify_service.get_playlist_tracks(access_token, playlist_id),
    )
    groups = track_identity_service.find_duplicates(tracks)
    duplicate_track_count = sum(len(group) - 1 for group in groups)
    return {
        "playlist_name": playlist["name"],
        "total_tracks": len(tracks),
        # schemas.playlist.DuplicateGroup is {"tracks": [...]}, not a bare
        # list — find_duplicates() returns list[list[dict]], so this must
        # wrap each group or response_model validation fails whenever there
        # actually ARE duplicates (the one case this endpoint exists for).
        "duplicate_groups": [{"tracks": group} for group in groups],
        "duplicate_track_count": duplicate_track_count,
    }


def _dedupe_tracks(tracks: list[dict]) -> tuple[list[dict], int]:
    kept: list[dict] = []
    removed = 0
    for track in tracks:
        if any(track_identity_service.is_same_track(track, k) for k in kept):
            removed += 1
        else:
            kept.append(track)
    return kept, removed


async def _collect_tracks(access_token: str, playlist_ids: list[str]) -> list[dict]:
    track_lists = await asyncio.gather(
        *(spotify_service.get_playlist_tracks(access_token, pid) for pid in playlist_ids)
    )
    all_tracks: list[dict] = []
    for tracks in track_lists:
        all_tracks.extend(tracks)
    return all_tracks


async def merge_preview(access_token: str, source_playlist_ids: list[str], dedupe: bool) -> dict:
    all_tracks = await _collect_tracks(access_token, source_playlist_ids)
    deduped, duplicates_removed = _dedupe_tracks(all_tracks) if dedupe else (all_tracks, 0)
    return {
        "tracks_to_add": len(deduped),
        "duplicates_removed": duplicates_removed,
        "sample": deduped[:20],
    }


async def merge_confirm(
    access_token: str,
    source_playlist_ids: list[str],
    dedupe: bool,
    destination_playlist_id: str | None,
    new_playlist_name: str | None,
) -> dict:
    all_tracks = await _collect_tracks(access_token, source_playlist_ids)
    deduped, _ = _dedupe_tracks(all_tracks) if dedupe else (all_tracks, 0)

    if destination_playlist_id:
        playlist = await spotify_service.get_playlist(access_token, destination_playlist_id)
    else:
        playlist = await spotify_service.create_playlist(access_token, new_playlist_name or "Playlist fusionada")

    uris = [t["uri"] for t in deduped]
    if uris:
        await spotify_service.add_tracks_to_playlist(access_token, playlist["id"], uris)

    return {"playlist_id": playlist["id"], "playlist_name": playlist["name"], "added_count": len(uris)}
