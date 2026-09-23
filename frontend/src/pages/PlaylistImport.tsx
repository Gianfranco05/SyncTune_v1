import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  confirmPlaylist,
  createPlaylist,
  getPlaylists,
  getYoutubeStatus,
  previewPlaylist,
  spotifyLoginUrl,
  youtubeLoginUrl,
} from '../api'
import { CONFIDENCE_LABEL, friendlyError } from '../format'
import { loadSettings, type SyncSettings } from '../settings'
import type { Playlist, PlaylistPreviewResponse, Sync, SpotifyTrackCandidate } from '../types'

// item_id -> chosen candidate, or null to skip that song.
type Selections = Record<number, SpotifyTrackCandidate | null>

export default function PlaylistImport() {
  const [settings] = useState<SyncSettings>(loadSettings)
  const isSimple = settings.displayMode === 'simple'
  const [youtubeConnected, setYoutubeConnected] = useState<boolean | null>(null)
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [preview, setPreview] = useState<PlaylistPreviewResponse | null>(null)
  const [selections, setSelections] = useState<Selections>({})
  const [playlists, setPlaylists] = useState<Playlist[]>([])
  const [selectedPlaylistId, setSelectedPlaylistId] = useState('')
  const [newPlaylistName, setNewPlaylistName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<Sync | null>(null)

  useEffect(() => {
    getYoutubeStatus()
      .then((me) => setYoutubeConnected(me.authenticated))
      .catch(() => setYoutubeConnected(false))
    getPlaylists().then(setPlaylists).catch(() => setPlaylists([]))
  }, [])

  async function handlePreview() {
    if (!youtubeUrl.trim()) return
    setLoading(true)
    setError(null)
    setPreview(null)
    setResult(null)
    try {
      const data = await previewPlaylist(youtubeUrl.trim())
      setPreview(data)
      const initial: Selections = {}
      for (const item of data.items) {
        initial[item.item_id] = item.candidates[0] ?? null
      }
      setSelections(initial)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  async function handleConfirm() {
    if (!preview) return
    setLoading(true)
    setError(null)
    try {
      let playlistId = selectedPlaylistId
      let playlistName = playlists.find((p) => p.id === selectedPlaylistId)?.name ?? ''
      if (!playlistId && newPlaylistName.trim()) {
        const created = await createPlaylist(newPlaylistName.trim())
        playlistId = created.id
        playlistName = created.name
        setPlaylists((prev) => [...prev, created])
        setSelectedPlaylistId(created.id)
        setNewPlaylistName('')
      }
      if (!playlistId) {
        setError('Elegí una playlist o creá una nueva antes de confirmar.')
        return
      }

      const sync = await confirmPlaylist(preview.sync_id, {
        playlist_id: playlistId,
        playlist_name: playlistName,
        selections: preview.items.map((item) => {
          const chosen = selections[item.item_id]
          return {
            item_id: item.item_id,
            track_id: chosen?.id ?? null,
            track_uri: chosen?.uri ?? null,
            track_name: chosen?.name ?? null,
            track_artists: chosen?.artists ?? null,
            confidence: chosen?.confidence ?? null,
            skip: !chosen,
          }
        }),
      })
      setResult(sync)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  if (youtubeConnected === false) {
    return (
      <div className="empty-state">
        <p>Para importar una playlist completa necesitás conectar tu cuenta de YouTube.</p>
        <a className="button" href={youtubeLoginUrl()}>
          Conectar YouTube
        </a>
      </div>
    )
  }

  if (result) {
    const counts = { imported: 0, duplicate: 0, skipped: 0 }
    for (const item of result.items) {
      if (item.status === 'imported') counts.imported++
      else if (item.status === 'duplicate') counts.duplicate++
      else if (item.status === 'skipped') counts.skipped++
    }
    return (
      <div className="result-banner">
        <p>
          ✓ {counts.imported} agregadas, {counts.duplicate} ya existían, {counts.skipped} ignoradas — playlist{' '}
          <strong>{result.destination_name}</strong>.
        </p>
        <Link to="/history">Ver en el historial</Link>
      </div>
    )
  }

  return (
    <div>
      <div className="search-row">
        <input
          type="text"
          placeholder="Pegá una URL de playlist de YouTube"
          value={youtubeUrl}
          onChange={(e) => setYoutubeUrl(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handlePreview()}
        />
        <button onClick={handlePreview} disabled={loading}>
          Buscar
        </button>
      </div>

      {error && (
        <p className="error">
          {error}{' '}
          {error.includes('YouTube') && (
            <a href={youtubeLoginUrl()} className="link-button">
              Reconectar YouTube
            </a>
          )}
          {error.includes('Spotify') && (
            <a href={spotifyLoginUrl()} className="link-button">
              Reconectar Spotify
            </a>
          )}
        </p>
      )}

      {preview && (
        <div className="results">
          <p className="video-title">
            Playlist: <strong>{preview.playlist_title}</strong> — {preview.total_video_count} canciones
            {preview.truncated && ` (se procesan las primeras ${preview.items.length})`}
          </p>

          <ul className="playlist-rows">
            {preview.items.map((item) => {
              const chosen = selections[item.item_id]
              return (
                <li key={item.item_id} className="playlist-row">
                  <div className="playlist-row-source">{item.video.title}</div>
                  {isSimple ? (
                    <div className="playlist-row-source">{chosen ? `${chosen.name} — ${chosen.artists}` : 'Ignorar'}</div>
                  ) : (
                    <select
                      value={chosen ? chosen.id : ''}
                      onChange={(e) => {
                        const candidate = item.candidates.find((c) => c.id === e.target.value) ?? null
                        setSelections((prev) => ({ ...prev, [item.item_id]: candidate }))
                      }}
                    >
                      <option value="">Ignorar</option>
                      {item.candidates.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name} — {c.artists} ({c.confidence.toFixed(0)}%)
                        </option>
                      ))}
                    </select>
                  )}
                  {!isSimple &&
                    (chosen ? (
                      <span
                        className={`badge badge-${chosen.confidence_level}`}
                        title={CONFIDENCE_LABEL[chosen.confidence_level]}
                      >
                        {chosen.confidence.toFixed(0)}%
                      </span>
                    ) : (
                      <span className="badge">—</span>
                    ))}
                </li>
              )
            })}
          </ul>

          <div className="playlist-picker">
            <select value={selectedPlaylistId} onChange={(e) => setSelectedPlaylistId(e.target.value)}>
              <option value="">Elegí una playlist destino</option>
              {playlists.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <span>o</span>
            <input
              type="text"
              placeholder="Nombre de playlist nueva"
              value={newPlaylistName}
              onChange={(e) => setNewPlaylistName(e.target.value)}
            />
          </div>

          <div className="preview-summary">
            <p>
              Se van a agregar {Object.values(selections).filter(Boolean).length} de {preview.items.length}{' '}
              canciones (el resto quedó en "Ignorar").
            </p>
            <button onClick={handleConfirm} disabled={loading}>
              Confirmar cambios
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
