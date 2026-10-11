import { useEffect, useState } from 'react'
import { getYoutubeStatus, spotifyDisconnect, youtubeDisconnect, youtubeLoginUrl } from '../api'
import type { SpotifyMe, YoutubeMe } from '../types'

function ConnectionCard({
  name,
  connection,
  connectHref,
  onDisconnect,
}: {
  name: string
  connection: SpotifyMe | YoutubeMe | null
  connectHref?: string
  onDisconnect: () => void
}) {
  const head = (
    <div className="connection-card-head">
      <span className={`connection-icon connection-icon-${name.toLowerCase()}`} aria-hidden="true">
        {name === 'Spotify' ? '♪' : '▶'}
      </span>
      <h3>{name}</h3>
    </div>
  )

  if (connection === null) {
    return (
      <div className="connection-card">
        {head}
        <p className="connection-account">Cargando...</p>
      </div>
    )
  }

  return (
    <div className="connection-card">
      {head}
      {connection.authenticated ? (
        <>
          <p className="connection-status connection-status-on">● Conectado</p>
          {connection.display_name && <p className="connection-account">Cuenta: {connection.display_name}</p>}
          <button className="link-button" onClick={onDisconnect}>
            Desconectar
          </button>
        </>
      ) : (
        <>
          <p className="connection-status connection-status-off">○ No conectado</p>
          {connectHref && (
            <a className="button" href={connectHref}>
              Conectar {name}
            </a>
          )}
        </>
      )}
    </div>
  )
}

export default function Connections({
  spotifyMe,
  onSpotifyChange,
}: {
  spotifyMe: SpotifyMe
  onSpotifyChange: (me: SpotifyMe) => void
}) {
  const [youtubeMe, setYoutubeMe] = useState<YoutubeMe | null>(null)

  useEffect(() => {
    getYoutubeStatus()
      .then(setYoutubeMe)
      .catch(() => setYoutubeMe({ authenticated: false }))
  }, [])

  async function handleDisconnectSpotify() {
    if (!confirm('Esto desconecta tu cuenta de Spotify de SyncTune y borra el token guardado. ¿Continuar?')) return
    await spotifyDisconnect()
    onSpotifyChange({ authenticated: false })
  }

  async function handleDisconnectYoutube() {
    await youtubeDisconnect()
    setYoutubeMe({ authenticated: false })
  }

  return (
    <div>
      <h2>Conexiones</h2>
      <p className="connections-note">
        Acá administrás qué cuentas están conectadas a SyncTune. Nunca mostramos tokens ni secretos — solo el estado
        y la cuenta conectada.
      </p>
      <div className="connections-grid">
        <ConnectionCard name="Spotify" connection={spotifyMe} onDisconnect={handleDisconnectSpotify} />
        <ConnectionCard
          name="YouTube"
          connection={youtubeMe}
          connectHref={youtubeLoginUrl()}
          onDisconnect={handleDisconnectYoutube}
        />
      </div>
      <p className="connections-note">
        YouTube usa una app de Google todavía sin verificar (uso personal): puede pedirte reconectar cada 7 días.
      </p>
    </div>
  )
}
