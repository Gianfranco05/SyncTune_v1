import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { confirmSync, createPlaylist, getPlaylists, previewSync, spotifyLoginUrl } from '../api'
import { CONFIDENCE_LABEL, friendlyError } from '../format'
import type { Playlist, Sync, SpotifyTrackCandidate, SyncPreviewResponse } from '../types'

export default function SongImport() {
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [preview, setPreview] = useState<SyncPreviewResponse | null>(null)
  const [selectedCandidate, setSelectedCandidate] = useState<SpotifyTrackCandidate | null>(null)
  const [playlists, setPlaylists] = useState<Playlist[]>([])
  const [selectedPlaylistId, setSelectedPlaylistId] = useState('')
  const [newPlaylistName, setNewPlaylistName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<Sync | null>(null)

  useEffect(() => {
    getPlaylists().then(setPlaylists).catch(() => setPlaylists([]))
  }, [])

  async function handlePreview() {
    if (!youtubeUrl.trim()) return
    setLoading(true)
    setError(null)
    setPreview(null)
    setSelectedCandidate(null)
    setResult(null)
    try {
      const data = await previewSync(youtubeUrl.trim())
      setPreview(data)
      if (data.candidates.length > 0) {
        setSelectedCandidate(data.candidates[0])
      }
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  async function handleConfirm() {
    if (!preview || !selectedCandidate) return
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
      const sync = await confirmSync(preview.sync_id, {
        track_id: selectedCandidate.id,
        track_uri: selectedCandidate.uri,
        track_name: selectedCandidate.name,
        track_artists: selectedCandidate.artists,
        confidence: selectedCandidate.confidence,
        playlist_id: playlistId,
        playlist_name: playlistName,
      })
      setResult(sync)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  const item = result?.items[0]

  return (
    <div>
      <div className="search-row">
        <input
          type="text"
          placeholder="Pegá una URL de YouTube"
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
          {error.includes('Reconectá') && (
            <a href={spotifyLoginUrl()} className="link-button">
              Reconectar Spotify
            </a>
          )}
        </p>
      )}

      {result && item && (
        <div className="result-banner">
          {item.status === 'duplicate' ? (
            <p>
              ⚠ "{item.destination_title}" ya estaba en <strong>{result.destination_name}</strong> — no se
              agregó de nuevo.
            </p>
          ) : (
            <p>
              ✓ "{item.destination_title}" se agregó a <strong>{result.destination_name}</strong>.
            </p>
          )}
          <Link to="/history">Ver en el historial</Link>
        </div>
      )}

      {preview && !result && (
        <div className="results">
          <p className="video-title">
            Video: <strong>{preview.video.title}</strong> — {preview.video.channel_title}
          </p>

          {preview.candidates.length === 0 && (
            <div className="empty-state">
              <p>No encontramos una coincidencia confiable para esta canción.</p>
            </div>
          )}

          <ul className="candidates">
            {preview.candidates.map((candidate) => (
              <li
                key={candidate.id}
                className={`candidate ${selectedCandidate?.id === candidate.id ? 'selected' : ''}`}
                onClick={() => setSelectedCandidate(candidate)}
              >
                {candidate.album_image && <img src={candidate.album_image} alt="" />}
                <div className="candidate-info">
                  <div className="candidate-name">{candidate.name}</div>
                  <div className="candidate-artists">{candidate.artists}</div>
                </div>
                <span
                  className={`badge badge-${candidate.confidence_level}`}
                  title={CONFIDENCE_LABEL[candidate.confidence_level]}
                >
                  {candidate.confidence.toFixed(0)}%
                </span>
              </li>
            ))}
          </ul>

          {selectedCandidate && (
            <div className="playlist-picker">
              <select value={selectedPlaylistId} onChange={(e) => setSelectedPlaylistId(e.target.value)}>
                <option value="">Elegí una playlist</option>
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
          )}

          {selectedCandidate && (
            <div className="preview-summary">
              <p>
                Se va a agregar <strong>{selectedCandidate.name}</strong> ({selectedCandidate.artists}) a{' '}
                <strong>
                  {playlists.find((p) => p.id === selectedPlaylistId)?.name || newPlaylistName || '(elegí una playlist)'}
                </strong>
                .
              </p>
              <button onClick={handleConfirm} disabled={loading}>
                Confirmar cambios
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
