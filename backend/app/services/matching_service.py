import re
from difflib import SequenceMatcher

# spec §17: confidence thresholds. Kept as module constants — there's no
# settings UI yet (that's FASE 12) so this is the one place to tune them.
CONFIDENCE_HIGH = 90.0
CONFIDENCE_MEDIUM = 70.0

# spec §19: best-effort version tags, checked against both the YouTube title
# and the Spotify candidate's track/album name.
_VERSION_KEYWORDS: dict[str, list[str]] = {
    "live": ["live", "en vivo"],
    "acoustic": ["acoustic", "acústico", "acustico", "unplugged"],
    "remix": ["remix"],
    "remastered": ["remaster"],
    "instrumental": ["instrumental"],
    "karaoke": ["karaoke"],
    "cover": ["cover"],
}

# Common bracketed/parenthetical noise added by uploaders (official channels,
# reuploads, lyric/subtitle versions, etc). Matched case-insensitively.
_NOISE_PATTERNS = [
    r"\(official\s*(music\s*)?video\)",
    r"\(official\s*audio\)",
    r"\(official\)",
    r"\(lyrics?\)",
    r"\(lyric\s*video\)",
    r"\(audio\)",
    r"\(hd\)",
    r"\(hq\)",
    r"\(4k\)",
    r"\(visualizer\)",
    r"\(sub\s*(español|espanol|ingles|english)?\)",
    r"\(subtitulado\)",
    r"\(subtitles?\)",
    r"\(letra\)",
    r"\(con\s*letra\)",
    r"\[official\s*(music\s*)?video\]",
    r"\[official\s*audio\]",
    r"\[lyrics?\]",
    r"\[hd\]",
    r"\[sub\s*(español|espanol|ingles|english)?\]",
    r"\[subtitulado\]",
    r"\[letra\]",
    r"official\s*music\s*video",
    r"official\s*video",
    r"official\s*audio",
    r"lyric\s*video",
    # Bare trailing tags (spec §15) — safe to strip because detect_version()
    # below always reads the ORIGINAL title, not this cleaned one, so
    # stripping "Remastered" here doesn't lose the version signal.
    r"\bremastered\b",
    r"\blyrics\b",
    r"\b4k\b",
    r"\bhd\b",
]

_NOISE_RE = re.compile("|".join(_NOISE_PATTERNS), re.IGNORECASE)

# Separators that typically split "Artist - Track" style titles.
_SEPARATORS = [" - ", " – ", " — ", " | "]


def clean_title(raw_title: str) -> str:
    cleaned = _NOISE_RE.sub("", raw_title)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = cleaned.strip(" -–—|\t")
    return cleaned.strip()


def guess_artist_track(cleaned_title: str) -> dict:
    for sep in _SEPARATORS:
        if sep in cleaned_title:
            artist, _, track = cleaned_title.partition(sep)
            return {"artist": artist.strip(), "track": track.strip()}
    return {"artist": None, "track": cleaned_title.strip()}


def build_search_queries(raw_title: str) -> list[str]:
    """Return candidate Spotify search queries, best guess first.

    We never trust the channel/uploader, only the video title, since the
    same song is commonly reuploaded by non-official channels with extra
    subtitle/lyric noise in the title.
    """
    cleaned = clean_title(raw_title)
    guess = guess_artist_track(cleaned)

    queries = []
    if guess["artist"]:
        queries.append(f"track:{guess['track']} artist:{guess['artist']}")
        queries.append(f"{guess['artist']} {guess['track']}")
    queries.append(cleaned)
    if cleaned != raw_title.strip():
        queries.append(raw_title.strip())

    # De-duplicate while preserving order.
    seen = set()
    unique_queries = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique_queries.append(q)
    return unique_queries


def detect_version(text: str) -> str | None:
    """Best-effort version tag (live/acoustic/remix/...) — spec §19."""
    lowered = text.lower()
    for version, keywords in _VERSION_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return version
    return None


def confidence_level(score: float) -> str:
    """Alta/media/baja — spec §17."""
    if score >= CONFIDENCE_HIGH:
        return "alta"
    if score >= CONFIDENCE_MEDIUM:
        return "media"
    return "baja"


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def score_candidate(
    video_title: str,
    video_duration_ms: int | None,
    candidate_name: str,
    candidate_artists: str,
    candidate_album: str,
    candidate_duration_ms: int | None,
) -> float:
    """Confidence score 0-100 for a Spotify candidate against a YouTube
    video title — spec §16: artista 40% + título 40% + duración 10% +
    versión 10%.
    """
    cleaned = clean_title(video_title)
    guess = guess_artist_track(cleaned)
    artist_guess = guess["artist"]
    title_guess = guess["track"]

    artist_score = _similarity(artist_guess, candidate_artists) if artist_guess else 0.5
    title_score = _similarity(title_guess, candidate_name)

    duration_score = 0.5
    if video_duration_ms and candidate_duration_ms:
        diff_ms = abs(video_duration_ms - candidate_duration_ms)
        duration_score = max(0.0, 1 - diff_ms / 15_000)

    video_version = detect_version(video_title)
    candidate_version = detect_version(candidate_name) or detect_version(candidate_album)
    if video_version == candidate_version:
        version_score = 1.0
    elif video_version is None or candidate_version is None:
        version_score = 0.5
    else:
        version_score = 0.0

    total = artist_score * 0.4 + title_score * 0.4 + duration_score * 0.1 + version_score * 0.1
    return round(total * 100, 1)
