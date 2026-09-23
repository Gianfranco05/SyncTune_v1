"""Orchestrates the YouTube -> Spotify flow end to end, for a single video
(spec §12-16, §20-21) and for a whole playlist (spec §8-9). Analyze,
persist a review-able Sync/SyncItem (spec §10, §25), confirm with duplicate
detection (spec §20-21).

This is the only place that combines youtube_service + spotify_service +
matching_service, so the pipeline isn't duplicated across endpoints
(Regla 4) — the playlist flow reuses the exact same per-video matching as
the single-video flow via `_match_candidates`.
"""

import asyncio
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models import Sync, SyncItem, SyncItemStatus, SyncStatus
from app.services import matching_service, spotify_service, youtube_service

# Synchronous, request/response processing (no background jobs yet — that's
# FASE 13). Each preview handles one BATCH of up to MAX_PLAYLIST_ITEMS
# songs so a request stays fast and Spotify search volume reasonable; a
# longer playlist is worked through batch by batch via `offset` /
# `next_offset` (each batch is its own reviewable, confirmable Sync).
MAX_PLAYLIST_ITEMS = 50
# Ceiling on how many playlist ids we page through on YouTube (1 quota unit
# per 50) — far above any personal playlist, but bounded.
_MAX_PLAYLIST_FETCH = 1000
_PLAYLIST_MATCH_CONCURRENCY = 5


async def _match_candidates(access_token: str, video: dict, limit: int) -> list[dict]:
    candidates: list[dict] = []
    seen_ids: set[str] = set()
    for query in matching_service.build_search_queries(video["title"]):
        results = await spotify_service.search_tracks(access_token, query, limit=5)
        for r in results:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                candidates.append(r)
        if len(candidates) >= 8:
            break

    for candidate in candidates:
        score = matching_service.score_candidate(
            video_title=video["title"],
            video_duration_ms=video["duration_ms"],
            candidate_name=candidate["name"],
            candidate_artists=candidate["artists"],
            candidate_album=candidate["album"],
            candidate_duration_ms=candidate["duration_ms"],
        )
        candidate["confidence"] = score
        candidate["confidence_level"] = matching_service.confidence_level(score)

    candidates.sort(key=lambda c: c["confidence"], reverse=True)
    return candidates[:limit]


async def analyze_youtube_video(access_token: str, url: str) -> dict:
    """Raises ValueError (bad URL) or youtube_service.VideoNotFoundError."""
    video_id = youtube_service.extract_video_id(url)
    video = await youtube_service.fetch_video_title(video_id)
    candidates = await _match_candidates(access_token, video, limit=5)
    return {"video": video, "candidates": candidates}


def create_pending_sync(db: Session, user_id: int, video: dict) -> Sync:
    sync = Sync(
        user_id=user_id,
        source="youtube",
        destination="spotify",
        source_name=video["title"],
        status=SyncStatus.review,
    )
    db.add(sync)
    db.flush()

    item = SyncItem(
        sync_id=sync.id,
        source_id=video["video_id"],
        source_title=video["title"],
        status=SyncItemStatus.review,
    )
    db.add(item)
    db.commit()
    db.refresh(sync)
    logger.info("sync_started", extra={"sync_id": sync.id, "user_id": user_id, "source": "video"})
    return sync


async def confirm_sync(
    db: Session,
    sync: Sync,
    access_token: str,
    track: dict,
    playlist_id: str,
    playlist_name: str,
) -> Sync:
    item = sync.items[0]

    existing_ids = await spotify_service.get_playlist_track_ids(access_token, playlist_id)
    is_duplicate = track["id"] in existing_ids

    if not is_duplicate:
        await spotify_service.add_track_to_playlist(access_token, playlist_id, track["uri"])

    item.destination_id = track["id"]
    item.destination_title = track["name"]
    item.destination_artist = track["artists"]
    item.confidence = track.get("confidence")
    item.status = SyncItemStatus.duplicate if is_duplicate else SyncItemStatus.imported

    sync.destination_name = playlist_name
    sync.status = SyncStatus.completed
    sync.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(sync)
    logger.info(
        "sync_completed",
        extra={"sync_id": sync.id, "status": item.status.value, "playlist_id": playlist_id},
    )
    return sync


async def analyze_youtube_playlist(spotify_token: str, youtube_token: str, url: str, offset: int = 0) -> dict:
    """Raises ValueError (bad URL) or youtube_service.PlaylistNotFoundError."""
    playlist_id = youtube_service.extract_playlist_id(url)
    title = await youtube_service.fetch_playlist_title(playlist_id, youtube_token)

    all_video_ids = await youtube_service.fetch_playlist_video_ids(
        playlist_id, youtube_token, max_items=_MAX_PLAYLIST_FETCH
    )
    video_ids = all_video_ids[offset : offset + MAX_PLAYLIST_ITEMS]
    next_offset = offset + MAX_PLAYLIST_ITEMS
    if next_offset >= len(all_video_ids):
        next_offset = None

    videos = await youtube_service.fetch_videos_bulk(video_ids)

    semaphore = asyncio.Semaphore(_PLAYLIST_MATCH_CONCURRENCY)

    async def _match_one(video: dict) -> dict:
        async with semaphore:
            candidates = await _match_candidates(spotify_token, video, limit=3)
        return {"video": video, "candidates": candidates}

    items = list(await asyncio.gather(*(_match_one(v) for v in videos)))

    return {
        "playlist_id": playlist_id,
        "title": title,
        "total_video_count": len(all_video_ids),
        "offset": offset,
        "next_offset": next_offset,
        "items": items,
    }


def create_pending_playlist_sync(
    db: Session, user_id: int, playlist_title: str, items: list[dict]
) -> tuple[Sync, list[int]]:
    sync = Sync(
        user_id=user_id,
        source="youtube",
        destination="spotify",
        source_name=playlist_title,
        status=SyncStatus.review,
    )
    db.add(sync)
    db.flush()

    item_ids: list[int] = []
    for entry in items:
        video = entry["video"]
        item = SyncItem(
            sync_id=sync.id,
            source_id=video["video_id"],
            source_title=video["title"],
            status=SyncItemStatus.review,
        )
        db.add(item)
        db.flush()
        item_ids.append(item.id)

    db.commit()
    db.refresh(sync)
    logger.info(
        "sync_started",
        extra={"sync_id": sync.id, "user_id": user_id, "source": "playlist", "item_count": len(item_ids)},
    )
    return sync, item_ids


async def confirm_playlist_sync(
    db: Session,
    sync: Sync,
    access_token: str,
    selections: list[dict],
    playlist_id: str,
    playlist_name: str,
) -> Sync:
    items_by_id = {item.id: item for item in sync.items}
    existing_ids = await spotify_service.get_playlist_track_ids(access_token, playlist_id)

    uris_to_add: list[str] = []
    seen_in_batch: set[str] = set()

    for selection in selections:
        item = items_by_id.get(selection["item_id"])
        if item is None:
            continue

        track_id = selection.get("track_id")
        if selection.get("skip") or not track_id:
            item.status = SyncItemStatus.skipped
            continue

        item.destination_id = track_id
        item.destination_title = selection.get("track_name")
        item.destination_artist = selection.get("track_artists")
        item.confidence = selection.get("confidence")

        if track_id in existing_ids or track_id in seen_in_batch:
            item.status = SyncItemStatus.duplicate
        else:
            item.status = SyncItemStatus.imported
            uris_to_add.append(selection["track_uri"])
            seen_in_batch.add(track_id)

    if uris_to_add:
        await spotify_service.add_tracks_to_playlist(access_token, playlist_id, uris_to_add)

    sync.destination_name = playlist_name
    sync.status = SyncStatus.completed
    sync.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(sync)
    logger.info(
        "sync_completed",
        extra={"sync_id": sync.id, "imported": len(uris_to_add), "playlist_id": playlist_id},
    )
    return sync
