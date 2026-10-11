import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { confirmSync, createPlaylist, getPlaylists, previewSync, spotifyLoginUrl } from '../api'
import { CONFIDENCE_LABEL, friendlyError } from '../format'
import { loadSettings, type SyncSettings } from '../settings'
import type { Playlist, Sync, SpotifyTrackCandidate, SyncPreviewResponse } from '../types'
import ManualSearch from './ManualSearch'

export default function SongImport() {
  const [settings] = useState<SyncSettings>(loadSettings)
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [preview, setPreview] = useState<SyncPreviewResponse | null>(null)
  const [selectedCandidate, setSelectedCandidate] = useState<SpotifyTrackCandidate | null>(null)
  const [playlists, setPlaylists] = useState<Playlist[]>([])
  const [selectedPlaylistId, setSelectedPlaylistId] = useState('')
  const [newPlaylistName, setNewPlaylistName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<Sync | null>(null)
  const autoConfirmedFor = useRef<number | null>(null)
  // Tracks picked by hand via "Buscar manualmente", listed next to the automatic candidates.
  const [manualCandidates, setManualCandidates] = useState<SpotifyTrackCandidate[]>([])
  const [showManual, setShowManual] = useState(false)

  const isSimple = settings.displayMode === 'simple'

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
    autoConfirmedFor.current = null
    setManualCandidates([])
    setShowManual(false)
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
        // A hand-picked track has no real match score to record.
        confidence: selectedCandidate.manual ? null : selectedCandidate.confidence,
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

  // Modo rápido (spec §22): once a destination playlist is picked, a
  // high-confidence single-song match confirms itself instead of waiting
  // for the extra click. Never applies to playlists (spec §21 — those are
  // a "big operation" and always need explicit confirmation).
  useEffect(() => {
    if (settings.safetyMode !== 'rapido') return
    if (!preview || !selectedCandidate || !selectedPlaylistId) return
    // A hand-picked track never auto-confirms: fast mode trusts the match
    // score, and a manual pick has none.
    if (selectedCandidate.manual || selectedCandidate.confidence < settings.fastModeThreshold) return
    if (autoConfirmedFor.current === preview.sync_id) return
    autoConfirmedFor.current = preview.sync_id
    handleConfirm()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPlaylistId, selectedCandidate, preview, settings.safetyMode, settings.fastModeThreshold])

  const item = result?.items[0]
  const allCandidates = preview ? [...preview.candidates, ...manualCandidates] : []
  const canSearchManually = !isSimple || (preview?.candidates.length ?? 0) === 0

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

          {isSimple ? (
            selectedCandidate && (
              <div className="candidate selected">
                {selectedCandidate.album_image && <img src={selectedCandidate.album_image} alt="" />}
                <div className="candidate-info">
                  <div className="candidate-name">{selectedCandidate.name}</div>
                  <div className="candidate-artists">{selectedCandidate.artists}</div>
                </div>
              </div>
            )
          ) : (
            <ul className="candidates">
              {allCandidates.map((candidate) => (
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
                    {candidate.manual ? 'manual' : `${candidate.confidence.toFixed(0)}%`}
                  </span>
                </li>
              ))}
            </ul>
          )}

          {canSearchManually && (
            <div className="manual-search-toggle">
              <button className="link-button" onClick={() => setShowManual((v) => !v)}>
                Buscar manualmente
              </button>
              {showManual && (
                <ManualSearch
                  onPick={(candidate) => {
                    setManualCandidates((prev) => [...prev, candidate])
                    setSelectedCandidate(candidate)
                    setShowManual(false)
                  }}
                />
              )}
            </div>
          )}

          {selectedCandidate && (
            <div className="playlist-picker">
              <select value={selectedPlaylistId} onChange={(e) => setSelectedPlaylistId(e.target.value)}>
                <option value="">Elegí una playlist</option>
                <optgroup label="♪ Spotify — tus playlists">
                  {playlists.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </optgroup>
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
