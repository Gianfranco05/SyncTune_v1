export interface SpotifyMe {
  authenticated: boolean
  id?: string | null
  display_name?: string | null
}

export interface YoutubeMe {
  authenticated: boolean
  id?: string | null
  display_name?: string | null
}

export interface YoutubeVideo {
  video_id: string
  title: string
  channel_title: string
  duration_ms: number | null
}

export type ConfidenceLevel = 'alta' | 'media' | 'baja'

export interface SpotifyTrackCandidate {
  id: string
  uri: string
  name: string
  artists: string
  album: string
  album_image: string | null
  external_url: string
  duration_ms: number
  confidence: number
  confidence_level: ConfidenceLevel
}

export interface Playlist {
  id: string
  name: string
}

export interface SyncPreviewResponse {
  sync_id: number
  video: YoutubeVideo
  candidates: SpotifyTrackCandidate[]
}

export type SyncStatus =
  | 'pending'
  | 'analyzing'
  | 'matching'
  | 'review'
  | 'importing'
  | 'completed'
  | 'partial'
  | 'failed'
  | 'cancelled'

export type SyncItemStatus =
  | 'matched'
  | 'review'
  | 'not_found'
  | 'selected'
  | 'skipped'
  | 'imported'
  | 'failed'
  | 'duplicate'

export interface SyncItem {
  id: number
  source_title: string
  source_artist: string | null
  destination_title: string | null
  destination_artist: string | null
  status: SyncItemStatus
  confidence: number | null
}

export interface Sync {
  id: number
  source: string
  destination: string
  source_name: string
  destination_name: string | null
  status: SyncStatus
  created_at: string
  completed_at: string | null
  items: SyncItem[]
}

export interface DashboardStats {
  songs_synced: number
  duplicates_skipped: number
  pending_review: number
  playlists_touched: number
  average_confidence: number | null
  last_sync_at: string | null
}

export interface DashboardResponse {
  stats: DashboardStats
  recent: Sync[]
}

export interface PlaylistPreviewItem {
  item_id: number
  video: YoutubeVideo
  candidates: SpotifyTrackCandidate[]
}

export interface PlaylistPreviewResponse {
  sync_id: number
  playlist_title: string
  total_video_count: number
  truncated: boolean
  items: PlaylistPreviewItem[]
}

export interface PlaylistSelection {
  item_id: number
  track_id: string | null
  track_uri: string | null
  track_name: string | null
  track_artists: string | null
  confidence: number | null
  skip: boolean
}

export interface PlaylistTrack {
  id: string
  uri: string
  name: string
  artists: string
  album: string
  album_image: string | null
  external_url: string
  duration_ms: number
}

export interface PlaylistCompareResponse {
  playlist_a_name: string
  playlist_b_name: string
  common: PlaylistTrack[]
  only_a: PlaylistTrack[]
  only_b: PlaylistTrack[]
}

export interface DuplicateGroup {
  tracks: PlaylistTrack[]
}

export interface PlaylistHealthResponse {
  playlist_name: string
  total_tracks: number
  duplicate_groups: DuplicateGroup[]
  duplicate_track_count: number
}

export interface MergePreviewResponse {
  tracks_to_add: number
  duplicates_removed: number
  sample: PlaylistTrack[]
}

export interface MergeConfirmResponse {
  playlist_id: string
  playlist_name: string
  added_count: number
}
