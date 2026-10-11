import { useEffect, useState } from 'react'
import { Link, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { getSpotifyMe, spotifyLogout } from './api'
import type { SpotifyMe } from './types'
import Home from './pages/Home'
import History from './pages/History'
import Connections from './pages/Connections'
import Dashboard from './pages/Dashboard'
import PlaylistTools from './pages/PlaylistTools'
import Settings from './pages/Settings'
import CommandPalette, { type PaletteAction } from './pages/CommandPalette'
import './App.css'

type Theme = 'system' | 'light' | 'dark'
const THEME_STORAGE_KEY = 'synctune-theme'
const THEME_CYCLE: Theme[] = ['system', 'light', 'dark']
const THEME_LABEL: Record<Theme, string> = { system: '🌓 Sistema', light: '☀️ Claro', dark: '🌙 Oscuro' }

function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      return (localStorage.getItem(THEME_STORAGE_KEY) as Theme | null) ?? 'system'
    } catch {
      return 'system'
    }
  })

  useEffect(() => {
    if (theme === 'system') {
      document.documentElement.removeAttribute('data-theme')
    } else {
      document.documentElement.setAttribute('data-theme', theme)
    }
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme)
    } catch {
      // Private browsing / storage blocked — theme just won't persist.
    }
  }, [theme])

  function cycleTheme() {
    setTheme((prev) => THEME_CYCLE[(THEME_CYCLE.indexOf(prev) + 1) % THEME_CYCLE.length])
  }

  return [theme, cycleTheme]
}

const OAUTH_ERROR_MESSAGE: Record<string, string> = {
  oauth_failed: 'No pudimos completar la conexión. Probá de nuevo.',
  no_channel: 'Esa cuenta de Google no tiene un canal de YouTube para conectar.',
  access_denied: 'Cancelaste la autorización, así que no se conectó la cuenta.',
}

function App() {
  const [me, setMe] = useState<SpotifyMe | null>(null)
  const [theme, cycleTheme] = useTheme()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [oauthError, setOauthError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    getSpotifyMe()
      .then(setMe)
      .catch(() => setMe({ authenticated: false }))
  }, [])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const code = params.get('spotify_error') ?? params.get('youtube_error')
    if (code) {
      setOauthError(OAUTH_ERROR_MESSAGE[code] ?? 'No pudimos completar la conexión. Probá de nuevo.')
      params.delete('spotify_error')
      params.delete('youtube_error')
      const query = params.toString()
      window.history.replaceState({}, '', window.location.pathname + (query ? `?${query}` : ''))
    }
  }, [])

  useEffect(() => {
    if (!me?.authenticated) return
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen(true)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [me?.authenticated])

  async function handleLogout() {
    await spotifyLogout()
    setMe({ authenticated: false })
  }

  if (me === null) {
    return <div className="container loading">Cargando...</div>
  }

  const paletteActions: PaletteAction[] = [
    { id: 'dashboard', label: 'Ir a Dashboard', run: () => navigate('/dashboard') },
    { id: 'song', label: 'Importar canción', run: () => navigate('/') },
    { id: 'playlist', label: 'Importar playlist', run: () => navigate('/') },
    { id: 'compare', label: 'Comparar playlists', run: () => navigate('/playlists') },
    { id: 'clean', label: 'Limpiar playlist (duplicados)', run: () => navigate('/playlists') },
    { id: 'history', label: 'Ver historial', run: () => navigate('/history') },
    { id: 'connections', label: 'Conexiones', run: () => navigate('/connections') },
    { id: 'settings', label: 'Configuración', run: () => navigate('/settings') },
    { id: 'theme', label: 'Cambiar tema', run: cycleTheme },
  ]

  return (
    <div className="container">
      <header className="header">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true">
            ♪
          </span>
          SyncTune
        </Link>
        {me.authenticated && (
          <>
            <nav className="nav">
              <NavLink to="/dashboard" className="nav-link">
                Dashboard
              </NavLink>
              <NavLink to="/" end className="nav-link">
                Sincronizar
              </NavLink>
              <NavLink to="/playlists" className="nav-link">
                Playlists
              </NavLink>
              <NavLink to="/history" className="nav-link">
                Historial
              </NavLink>
              <NavLink to="/connections" className="nav-link">
                Conexiones
              </NavLink>
              <NavLink to="/settings" className="nav-link">
                Config
              </NavLink>
            </nav>
            <div className="header-actions">
              <button className="button-ghost" onClick={cycleTheme} title="Cambiar tema (Ctrl+K para más acciones)">
                {THEME_LABEL[theme]}
              </button>
              <span className="user-chip" title={me.display_name ?? me.id ?? undefined}>
                {me.display_name ?? me.id}
              </span>
              <button className="button-ghost" onClick={handleLogout}>
                Cerrar sesión
              </button>
            </div>
          </>
        )}
      </header>

      {paletteOpen && <CommandPalette actions={paletteActions} onClose={() => setPaletteOpen(false)} />}

      {oauthError && (
        <p className="error" role="alert">
          {oauthError}{' '}
          <button className="link-button" onClick={() => setOauthError(null)}>
            Cerrar
          </button>
        </p>
      )}

      <Routes>
        <Route path="/" element={<Home me={me} />} />
        <Route path="/dashboard" element={me.authenticated ? <Dashboard /> : <Home me={me} />} />
        <Route path="/playlists" element={me.authenticated ? <PlaylistTools /> : <Home me={me} />} />
        <Route path="/history" element={me.authenticated ? <History /> : <Home me={me} />} />
        <Route
          path="/connections"
          element={me.authenticated ? <Connections spotifyMe={me} onSpotifyChange={setMe} /> : <Home me={me} />}
        />
        <Route path="/settings" element={me.authenticated ? <Settings /> : <Home me={me} />} />
      </Routes>
    </div>
  )
}

export default App
