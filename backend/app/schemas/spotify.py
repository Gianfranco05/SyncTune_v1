from pydantic import BaseModel


class SpotifyMe(BaseModel):
    authenticated: bool
    id: str | None = None
    display_name: str | None = None


class SpotifyTrackCandidate(BaseModel):
    id: str
    uri: str
    name: str
    artists: str
    album: str
    album_image: str | None
    external_url: str
    duration_ms: int
    confidence: float
    confidence_level: str


class Playlist(BaseModel):
    id: str
    name: str


class CreatePlaylistRequest(BaseModel):
    name: str


class AddTrackRequest(BaseModel):
    track_uri: str
