"""Determines whether two Spotify tracks represent "potentially the same
song" — spec §16: comparator + duplicate detection need this, not a raw ID
equality check (the same song can appear as two different Spotify track
IDs — a single vs. an album cut, a remaster, etc.).

We compare by normalized title+artist similarity only (no ISRC): the
Spotify catalog fields available after the Feb 2026 Development Mode
migration (see IMPLEMENTATION_PLAN.md FASE 0) were verified for what this
project already uses (search, playlists) but `external_ids.isrc` was never
confirmed as still exposed, so we didn't build on an unverified field
(Regla 71). If it's confirmed available later, ISRC equality is a strictly
better signal than title/artist and could tighten this.
"""

from difflib import SequenceMatcher

SAME_TRACK_THRESHOLD = 0.85


def _norm(text: str) -> str:
    return text.lower().strip()


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def is_same_track(track_a: dict, track_b: dict) -> bool:
    if track_a.get("id") and track_a["id"] == track_b.get("id"):
        return True
    return (
        _similarity(track_a["name"], track_b["name"]) >= SAME_TRACK_THRESHOLD
        and _similarity(track_a["artists"], track_b["artists"]) >= SAME_TRACK_THRESHOLD
    )


def compare_track_lists(tracks_a: list[dict], tracks_b: list[dict]) -> dict:
    """spec §15-16: playlist comparator (coinciden / solo en A / solo en B)."""
    matched_b_indices: set[int] = set()
    common: list[dict] = []
    only_a: list[dict] = []

    for track_a in tracks_a:
        match_index = None
        for i, track_b in enumerate(tracks_b):
            if i in matched_b_indices:
                continue
            if is_same_track(track_a, track_b):
                match_index = i
                break
        if match_index is not None:
            matched_b_indices.add(match_index)
            common.append(track_a)
        else:
            only_a.append(track_a)

    only_b = [track_b for i, track_b in enumerate(tracks_b) if i not in matched_b_indices]
    return {"common": common, "only_a": only_a, "only_b": only_b}


def find_duplicates(tracks: list[dict]) -> list[list[dict]]:
    """spec §18-19: groups of 2+ tracks within one list considered the same
    song (e.g. a track added twice, or as two different versions)."""
    groups: list[list[dict]] = []
    used: set[int] = set()

    for i, track in enumerate(tracks):
        if i in used:
            continue
        group = [track]
        for j in range(i + 1, len(tracks)):
            if j in used:
                continue
            if is_same_track(track, tracks[j]):
                group.append(tracks[j])
                used.add(j)
        if len(group) > 1:
            used.add(i)
            groups.append(group)

    return groups
