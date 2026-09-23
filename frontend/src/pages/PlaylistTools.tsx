import { useEffect, useState } from 'react'
import {
  comparePlaylists,
  getPlaylistHealth,
  getPlaylists,
  mergeConfirm,
  mergePreview,
} from '../api'
import { friendlyError } from '../format'
import type {
  MergeConfirmResponse,
  MergePreviewResponse,
  Playlist,
  PlaylistCompareResponse,
  PlaylistHealthResponse,
} from '../types'

type Tab = 'compare' | 'health' | 'merge'

function TrackList({ tracks }: { tracks: { id: string; name: string; artists: string }[] }) {
  if (tracks.length === 0) return <p className="empty-hint">Ninguna</p>
  return (
    <ul className="track-list">
      {tracks.map((t) => (
        <li key={t.id}>
          {t.name} <span className="track-artists">— {t.artists}</span>
        </li>
      ))}
    </ul>
  )
}

function ComparePanel({ playlists }: { playlists: Playlist[] }) {
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [result, setResult] = useState<PlaylistCompareResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleCompare() {
    if (!a || !b) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      setResult(await comparePlaylists(a, b))
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="playlist-picker">
        <select value={a} onChange={(e) => setA(e.target.value)}>
          <option value="">Playlist A</option>
          {playlists.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <select value={b} onChange={(e) => setB(e.target.value)}>
          <option value="">Playlist B</option>
          {playlists.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <button onClick={handleCompare} disabled={loading || !a || !b}>
          Comparar
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {result && (
        <div className="compare-grid">
          <div>
            <h4>Coinciden ({result.common.length})</h4>
            <TrackList tracks={result.common} />
          </div>
          <div>
            <h4>
              Solo en {result.playlist_a_name} ({result.only_a.length})
            </h4>
            <TrackList tracks={result.only_a} />
          </div>
          <div>
            <h4>
              Solo en {result.playlist_b_name} ({result.only_b.length})
            </h4>
            <TrackList tracks={result.only_b} />
          </div>
        </div>
      )}
    </div>
  )
}

function HealthPanel({ playlists }: { playlists: Playlist[] }) {
  const [playlistId, setPlaylistId] = useState('')
  const [result, setResult] = useState<PlaylistHealthResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleAnalyze() {
    if (!playlistId) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      setResult(await getPlaylistHealth(playlistId))
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="playlist-picker">
        <select value={playlistId} onChange={(e) => setPlaylistId(e.target.value)}>
          <option value="">Elegí una playlist</option>
          {playlists.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <button onClick={handleAnalyze} disabled={loading || !playlistId}>
          Analizar
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {result && (
        <div className="health-report">
          <p>
            <strong>{result.playlist_name}</strong> — {result.total_tracks} canciones,{' '}
            {result.duplicate_track_count} duplicadas
          </p>
          {result.duplicate_groups.length === 0 ? (
            <p className="empty-hint">Sin duplicados.</p>
          ) : (
            <ul className="track-list">
              {result.duplicate_groups.map((group, i) => (
                <li key={i}>
                  {group.tracks.map((t) => `${t.name} — ${t.artists}`).join('  ≈  ')}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

function MergePanel({ playlists }: { playlists: Playlist[] }) {
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [dedupe, setDedupe] = useState(true)
  const [destinationId, setDestinationId] = useState('')
  const [newName, setNewName] = useState('')
  const [preview, setPreview] = useState<MergePreviewResponse | null>(null)
  const [result, setResult] = useState<MergeConfirmResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
    setPreview(null)
  }

  async function handlePreview() {
    if (selected.size < 2) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      setPreview(await mergePreview([...selected], dedupe))
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  async function handleConfirm() {
    if (!preview) return
    if (!destinationId && !newName.trim()) {
      setError('Elegí una playlist destino o poné un nombre para la nueva.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      setResult(
        await mergeConfirm({
          source_playlist_ids: [...selected],
          dedupe,
          destination_playlist_id: destinationId || undefined,
          new_playlist_name: destinationId ? undefined : newName.trim(),
        }),
      )
      setPreview(null)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  if (result) {
    return (
      <p className="result-banner">
        ✓ {result.added_count} canciones agregadas a <strong>{result.playlist_name}</strong>.
      </p>
    )
  }

  return (
    <div>
      <p>Elegí 2 o más playlists para fusionar:</p>
      <ul className="checkbox-list">
        {playlists.map((p) => (
          <li key={p.id}>
            <label>
              <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggle(p.id)} />
              {p.name}
            </label>
          </li>
        ))}
      </ul>

      <label className="checkbox-inline">
        <input type="checkbox" checked={dedupe} onChange={(e) => setDedupe(e.target.checked)} />
        Evitar duplicados
      </label>

      {error && <p className="error">{error}</p>}

      {!preview && (
        <button onClick={handlePreview} disabled={loading || selected.size < 2}>
          Vista previa
        </button>
      )}

      {preview && (
        <div className="preview-summary">
          <p>
            Se agregarán {preview.tracks_to_add} canciones ({preview.duplicates_removed} duplicados descartados).
          </p>
          <div className="playlist-picker">
            <select value={destinationId} onChange={(e) => setDestinationId(e.target.value)}>
              <option value="">Playlist destino existente</option>
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
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
          </div>
          <button onClick={handleConfirm} disabled={loading}>
            Confirmar fusión
          </button>
        </div>
      )}
    </div>
  )
}

export default function PlaylistTools() {
  const [tab, setTab] = useState<Tab>('compare')
  const [playlists, setPlaylists] = useState<Playlist[]>([])

  useEffect(() => {
    getPlaylists().then(setPlaylists).catch(() => setPlaylists([]))
  }, [])

  return (
    <div>
      <h2>Playlists</h2>
      <div className="import-mode-switch">
        <button className={tab === 'compare' ? 'mode-active' : ''} onClick={() => setTab('compare')}>
          Comparar
        </button>
        <button className={tab === 'health' ? 'mode-active' : ''} onClick={() => setTab('health')}>
          Salud / duplicados
        </button>
        <button className={tab === 'merge' ? 'mode-active' : ''} onClick={() => setTab('merge')}>
          Fusionar
        </button>
      </div>

      {tab === 'compare' && <ComparePanel playlists={playlists} />}
      {tab === 'health' && <HealthPanel playlists={playlists} />}
      {tab === 'merge' && <MergePanel playlists={playlists} />}
    </div>
  )
}
