from pydantic import BaseModel


class YoutubeMe(BaseModel):
    authenticated: bool
    id: str | None = None
    display_name: str | None = None


class YoutubePlaylist(BaseModel):
    id: str
    title: str
    video_count: int | None = None
    thumbnail: str | None = None


class YoutubeVideo(BaseModel):
    video_id: str
    title: str
    channel_title: str
    duration_ms: int | None = None
