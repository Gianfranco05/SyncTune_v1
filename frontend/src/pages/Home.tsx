import { useState } from 'react'
import { spotifyLoginUrl } from '../api'
import type { SpotifyMe } from '../types'
import SongImport from './SongImport'
import PlaylistImport from './PlaylistImport'

type ImportMode = 'song' | 'playlist'

export default function Home({ me }: { me: SpotifyMe }) {
  const [mode, setMode] = useState<ImportMode>('song')

  if (!me.authenticated) {
    return (
      <div className="onboarding">
        <div className="onboarding-logo" aria-hidden="true">
          ♪
        </div>
        <h1>Bienvenido a SyncTune</h1>
        <p>Conectá Spotify para empezar a traer canciones desde YouTube.</p>
        <ol className="onboarding-steps">
          <li>
            <span>1. Spotify</span>
            <a className="button button-lg" href={spotifyLoginUrl()}>
              Conectar
            </a>
          </li>
        </ol>
        <div className="feature-list">
          <div className="feature">
            <strong>Coincidencias claras</strong>
            <span>Cada canción llega con su % de confianza.</span>
          </div>
          <div className="feature">
            <strong>Sin duplicados</strong>
            <span>Te avisamos antes de agregar algo repetido.</span>
          </div>
          <div className="feature">
            <strong>Vos confirmás</strong>
            <span>Nada se toca en Spotify sin tu visto bueno.</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="import-mode-switch">
        <button className={mode === 'song' ? 'mode-active' : ''} onClick={() => setMode('song')}>
          🎵 Canción
        </button>
        <button className={mode === 'playlist' ? 'mode-active' : ''} onClick={() => setMode('playlist')}>
          📋 Playlist
        </button>
      </div>
      {mode === 'song' ? <SongImport /> : <PlaylistImport />}
    </div>
  )
}
