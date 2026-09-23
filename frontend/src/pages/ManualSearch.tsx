import { useState } from 'react'
import { searchTracks } from '../api'
import { friendlyError } from '../format'
import type { PlaylistTrack, SpotifyTrackCandidate } from '../types'

export function toManualCandidate(track: PlaylistTrack): SpotifyTrackCandidate {
  return { ...track, confidence: 100, confidence_level: 'alta', manual: true }
}

// Free-text Spotify search for when none of the automatic candidates is
// right (spec §9: "buscar manualmente").
export default function ManualSearch({ onPick }: { onPick: (candidate: SpotifyTrackCandidate) => void }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<PlaylistTrack[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSearch() {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      setResults(await searchTracks(query.trim()))
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="manual-search">
      <div className="search-row">
        <input
          type="text"
          placeholder="Buscar canción en Spotify"
          aria-label="Buscar canción en Spotify"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
        />
        <button onClick={handleSearch} disabled={loading}>
          Buscar
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {results !== null && results.length === 0 && <p className="empty-hint">Sin resultados.</p>}
      {results && results.length > 0 && (
        <ul className="track-list manual-results">
          {results.map((track) => (
            <li key={track.id}>
              <button className="link-button" onClick={() => onPick(toManualCandidate(track))}>
                {track.name} <span className="track-artists">— {track.artists}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
