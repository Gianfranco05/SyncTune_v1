import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getDashboard } from '../api'
import { formatDate, SYNC_STATUS_LABEL } from '../format'
import type { DashboardResponse } from '../types'

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="stat-tile">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState<DashboardResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getDashboard()
      .then(setData)
      .catch(() => setError('No pudimos cargar el dashboard.'))
  }, [])

  if (error) return <p className="error">{error}</p>
  if (data === null) return <p>Cargando...</p>

  const { stats, recent } = data

  const noActivity = recent.length === 0

  return (
    <div>
      <h2>Dashboard</h2>

      {noActivity ? (
        <div className="empty-state">
          <p>Todavía no sincronizaste ninguna canción.</p>
          <Link className="button" to="/">
            Importar canción
          </Link>
        </div>
      ) : (
        <>
          <div className="stats-grid">
            <StatTile label="Canciones sincronizadas" value={stats.songs_synced} />
            <StatTile label="Playlists con canciones agregadas" value={stats.playlists_touched} />
            <StatTile label="Duplicados evitados" value={stats.duplicates_skipped} />
            <StatTile label="Revisiones pendientes" value={stats.pending_review} />
            <StatTile
              label="Confianza promedio"
              value={stats.average_confidence != null ? `${stats.average_confidence.toFixed(0)}%` : '—'}
            />
            <StatTile
              label="Última sincronización"
              value={stats.last_sync_at ? formatDate(stats.last_sync_at) : '—'}
            />
          </div>

          <h3>Actividad reciente</h3>
          <ul className="history-list">
            {recent.map((sync) => (
              <li key={sync.id} className="history-item">
                <div className="history-main">
                  <strong>{sync.source_name}</strong>
                  <span className={`status status-${sync.status}`}>
                    {SYNC_STATUS_LABEL[sync.status] ?? sync.status}
                  </span>
                </div>
                <div className="history-meta">
                  {sync.destination_name && <span>Playlist: {sync.destination_name} · </span>}
                  {formatDate(sync.created_at)}
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
