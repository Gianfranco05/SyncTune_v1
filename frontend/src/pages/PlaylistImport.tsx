import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  confirmPlaylist,
  createPlaylist,
  getPlaylists,
  getYoutubePlaylists,
  getYoutubeStatus,
  previewPlaylist,
  spotifyLoginUrl,
  youtubeLoginUrl,
} from '../api'
import { CONFIDENCE_LABEL, friendlyError } from '../format'
import { loadSettings, type SyncSettings } from '../settings'
import type { Playlist, PlaylistPreviewResponse, Sync, SpotifyTrackCandidate, YoutubePlaylist } from '../types'
import ManualSearch from './ManualSearch'

// item_id -> chosen candidate, or null to skip that song.
type Selections = Record<number, SpotifyTrackCandidate | null>

export default function PlaylistImport() {
  const [settings] = useState<SyncSettings>(loadSettings)
  const isSimple = settings.displayMode === 'simple'
  const [youtubeConnected, setYoutubeConnected] = useState<boolean | null>(null)
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [preview, setPreview] = useState<PlaylistPreviewResponse | null>(null)
  const [selections, setSelections] = useState<Selections>({})
  // Candidates picked by hand, per item — offered in that row's dropdown.
  const [manualCandidates, setManualCandidates] = useState<Record<number, SpotifyTrackCandidate[]>>({})
  const [searchingItem, setSearchingItem] = useState<number | null>(null)
  const [playlists, setPlaylists] = useState<Playlist[]>([])
  const [youtubePlaylists, setYoutubePlaylists] = useState<YoutubePlaylist[]>([])
  const [selectedPlaylistId, setSelectedPlaylistId] = useState('')
  const [newPlaylistName, setNewPlaylistName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<Sync | null>(null)

  useEffect(() => {
    getYoutubeStatus()
      .then((me) => {
        setYoutubeConnected(me.authenticated)
        if (me.authenticated) {
          // Best effort: without the list the user can still paste a URL.
          getYoutubePlaylists()
            .then(setYoutubePlaylists)
            .catch(() => setYoutubePlaylists([]))
        }
      })
      .catch(() => setYoutubeConnected(false))
    getPlaylists().then(setPlaylists).catch(() => setPlaylists([]))
  }, [])

  async function handlePreview(offset = 0, urlOverride?: string) {
    const url = (urlOverride ?? youtubeUrl).trim()
    if (!url) return
    setLoading(true)
    setError(null)
    setPreview(null)
    setResult(null)
    setManualCandidates({})
    setSearchingItem(null)
    try {
      const data = await previewPlaylist(url, offset)
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
            // A hand-picked track has no real match score to record.
            confidence: chosen && !chosen.manual ? chosen.confidence : null,
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

  function pickManual(itemId: number, candidate: SpotifyTrackCandidate) {
    setManualCandidates((prev) => ({ ...prev, [itemId]: [...(prev[itemId] ?? []), candidate] }))
    setSelections((prev) => ({ ...prev, [itemId]: candidate }))
    setSearchingItem(null)
  }

  function pickYoutubePlaylist(id: string) {
    if (!id) return
    const url = `https://www.youtube.com/playlist?list=${id}`
    setYoutubeUrl(url)
    handlePreview(0, url)
  }

  const nextBatch =
    preview && preview.next_offset !== null ? (
      <button onClick={() => handlePreview(preview.next_offset ?? 0)} disabled={loading}>
        Procesar las siguientes canciones ({preview.next_offset + 1}–
        {Math.min(preview.next_offset + (preview.next_offset - preview.offset), preview.total_video_count)} de{' '}
        {preview.total_video_count})
      </button>
    ) : null

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
        {nextBatch && <p>{nextBatch}</p>}
        <Link to="/history">Ver en el historial</Link>
      </div>
    )
  }

  return (
    <div>
      {youtubePlaylists.length > 0 && (
        <div className="source-picker">
          <label htmlFor="youtube-playlist">Origen · YouTube</label>
          <select
            id="youtube-playlist"
            value=""
            disabled={loading}
            onChange={(e) => pickYoutubePlaylist(e.target.value)}
          >
            <option value="">Elegí una de tus playlists de YouTube</option>
            <optgroup label="▶ YouTube — tus playlists">
              {youtubePlaylists.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title}
                  {p.video_count != null ? ` (${p.video_count})` : ''}
                </option>
              ))}
            </optgroup>
          </select>
          <span className="source-picker-or">o pegá una URL:</span>
        </div>
      )}
      <div className="search-row">
        <input
          type="text"
          placeholder="Pegá una URL de playlist de YouTube"
          value={youtubeUrl}
          onChange={(e) => setYoutubeUrl(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handlePreview()}
        />
        <button onClick={() => handlePreview()} disabled={loading}>
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
            {(preview.next_offset !== null || preview.offset > 0) &&
              ` (esta tanda: ${preview.offset + 1}–${preview.offset + preview.items.length})`}
          </p>

          <ul className="playlist-rows">
            {preview.items.map((item) => {
              const chosen = selections[item.item_id]
              const options = [...item.candidates, ...(manualCandidates[item.item_id] ?? [])]
              const canSearch = !isSimple || item.candidates.length === 0
              return (
                <li key={item.item_id} className="playlist-row">
                  <div className="playlist-row-source">{item.video.title}</div>
                  {isSimple ? (
                    <div className="playlist-row-source">{chosen ? `${chosen.name} — ${chosen.artists}` : 'Ignorar'}</div>
                  ) : (
                    <select
                      aria-label={`Coincidencia para ${item.video.title}`}
                      value={chosen ? chosen.id : ''}
                      onChange={(e) => {
                        const candidate = options.find((c) => c.id === e.target.value) ?? null
                        setSelections((prev) => ({ ...prev, [item.item_id]: candidate }))
                      }}
                    >
                      <option value="">Ignorar</option>
                      {options.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name} — {c.artists}
                          {c.manual ? ' (manual)' : ` (${c.confidence.toFixed(0)}%)`}
                        </option>
                      ))}
                    </select>
                  )}
                  {!isSimple &&
                    (chosen ? (
                      chosen.manual ? (
                        <span className="badge">manual</span>
                      ) : (
                        <span
                          className={`badge badge-${chosen.confidence_level}`}
                          title={CONFIDENCE_LABEL[chosen.confidence_level]}
                        >
                          {chosen.confidence.toFixed(0)}%
                        </span>
                      )
                    ) : (
                      <span className="badge">—</span>
                    ))}
                  {canSearch && (
                    <div className="playlist-row-manual">
                      <button
                        className="link-button"
                        onClick={() => setSearchingItem(searchingItem === item.item_id ? null : item.item_id)}
                      >
                        Buscar manualmente
                      </button>
                      {searchingItem === item.item_id && (
                        <ManualSearch onPick={(candidate) => pickManual(item.item_id, candidate)} />
                      )}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>

          <div className="playlist-picker">
            <select
              aria-label="Playlist destino en Spotify"
              value={selectedPlaylistId}
              onChange={(e) => setSelectedPlaylistId(e.target.value)}
            >
              <option value="">Elegí una playlist destino</option>
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

          <div className="preview-summary">
            <p>
              Se van a agregar {Object.values(selections).filter(Boolean).length} de {preview.items.length}{' '}
              canciones (el resto quedó en "Ignorar").
              {preview.next_offset !== null && ' Después de confirmar podés seguir con la siguiente tanda.'}
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
