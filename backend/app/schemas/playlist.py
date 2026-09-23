from pydantic import BaseModel


class PlaylistTrack(BaseModel):
    id: str
    uri: str
    name: str
    artists: str
    album: str
    album_image: str | None
    external_url: str
    duration_ms: int


class PlaylistCompareResponse(BaseModel):
    playlist_a_name: str
    playlist_b_name: str
    common: list[PlaylistTrack]
    only_a: list[PlaylistTrack]
    only_b: list[PlaylistTrack]


class DuplicateGroup(BaseModel):
    tracks: list[PlaylistTrack]


class PlaylistHealthResponse(BaseModel):
    playlist_name: str
    total_tracks: int
    duplicate_groups: list[DuplicateGroup]
    duplicate_track_count: int


class MergePreviewRequest(BaseModel):
    source_playlist_ids: list[str]
    dedupe: bool = True


class MergePreviewResponse(BaseModel):
    tracks_to_add: int
    duplicates_removed: int
    sample: list[PlaylistTrack]


class MergeConfirmRequest(BaseModel):
    source_playlist_ids: list[str]
    dedupe: bool = True
    destination_playlist_id: str | None = None
    new_playlist_name: str | None = None


class MergeConfirmResponse(BaseModel):
    playlist_id: str
    playlist_name: str
    added_count: int
