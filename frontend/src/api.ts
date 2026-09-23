import type {
  DashboardResponse,
  MergeConfirmResponse,
  MergePreviewResponse,
  Playlist,
  PlaylistCompareResponse,
  PlaylistHealthResponse,
  PlaylistPreviewResponse,
  PlaylistSelection,
  Sync,
  SpotifyMe,
  SyncPreviewResponse,
  YoutubeMe,
} from './types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL as string

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new ApiError(response.status, body.detail || 'Ocurrió un error inesperado.')
  }
  return response.json() as Promise<T>
}

export function spotifyLoginUrl(): string {
  return `${BASE_URL}/api/spotify/login`
}

export function getSpotifyMe(): Promise<SpotifyMe> {
  return request('/api/spotify/me')
}

export function spotifyLogout(): Promise<{ ok: boolean }> {
  return request('/api/spotify/logout', { method: 'POST' })
}

export function spotifyDisconnect(): Promise<{ ok: boolean }> {
  return request('/api/spotify/disconnect', { method: 'POST' })
}

export function youtubeLoginUrl(): string {
  return `${BASE_URL}/api/youtube/login`
}

export function getYoutubeStatus(): Promise<YoutubeMe> {
  return request('/api/youtube/status')
}

export function youtubeDisconnect(): Promise<{ ok: boolean }> {
  return request('/api/youtube/disconnect', { method: 'POST' })
}

export function getPlaylists(): Promise<Playlist[]> {
  return request('/api/spotify/playlists')
}

export function createPlaylist(name: string): Promise<Playlist> {
  return request('/api/spotify/playlists', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}

export function previewSync(youtubeUrl: string): Promise<SyncPreviewResponse> {
  return request('/api/sync/preview', {
    method: 'POST',
    body: JSON.stringify({ youtube_url: youtubeUrl }),
  })
}

export interface ConfirmSyncBody {
  track_id: string
  track_uri: string
  track_name: string
  track_artists: string
  confidence: number
  playlist_id: string
  playlist_name: string
}

export function confirmSync(syncId: number, body: ConfirmSyncBody): Promise<Sync> {
  return request(`/api/sync/${syncId}/confirm`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function getSyncHistory(): Promise<Sync[]> {
  return request('/api/sync/history')
}

export function getSyncDetail(syncId: number): Promise<Sync> {
  return request(`/api/sync/${syncId}`)
}

export function getDashboard(): Promise<DashboardResponse> {
  return request('/api/dashboard')
}

export function previewPlaylist(youtubeUrl: string): Promise<PlaylistPreviewResponse> {
  return request('/api/sync/playlist/preview', {
    method: 'POST',
    body: JSON.stringify({ youtube_url: youtubeUrl }),
  })
}

export function confirmPlaylist(
  syncId: number,
  body: { playlist_id: string; playlist_name: string; selections: PlaylistSelection[] },
): Promise<Sync> {
  return request(`/api/sync/${syncId}/playlist/confirm`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function comparePlaylists(playlistAId: string, playlistBId: string): Promise<PlaylistCompareResponse> {
  const params = new URLSearchParams({ playlist_a_id: playlistAId, playlist_b_id: playlistBId })
  return request(`/api/playlists/compare?${params}`)
}

export function getPlaylistHealth(playlistId: string): Promise<PlaylistHealthResponse> {
  return request(`/api/playlists/${playlistId}/health`)
}

export function mergePreview(sourcePlaylistIds: string[], dedupe: boolean): Promise<MergePreviewResponse> {
  return request('/api/playlists/merge/preview', {
    method: 'POST',
    body: JSON.stringify({ source_playlist_ids: sourcePlaylistIds, dedupe }),
  })
}

export function mergeConfirm(body: {
  source_playlist_ids: string[]
  dedupe: boolean
  destination_playlist_id?: string
  new_playlist_name?: string
}): Promise<MergeConfirmResponse> {
  return request('/api/playlists/merge/confirm', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
