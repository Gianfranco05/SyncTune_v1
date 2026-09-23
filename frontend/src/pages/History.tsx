import { useEffect, useState } from 'react'
import { getSyncHistory } from '../api'
import { formatDate, SYNC_STATUS_LABEL } from '../format'
import type { Sync } from '../types'

export default function History() {
  const [syncs, setSyncs] = useState<Sync[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getSyncHistory()
      .then(setSyncs)
      .catch(() => setError('No pudimos cargar el historial.'))
  }, [])

  if (error) return <p className="error">{error}</p>
  if (syncs === null) return <p>Cargando...</p>

  if (syncs.length === 0) {
    return (
      <div className="empty-state">
        <p>Todavía no sincronizaste ninguna canción.</p>
      </div>
    )
  }

  return (
    <ul className="history-list">
      {syncs.map((sync) => {
        // A playlist sync can have many items — a single video sync has
        // exactly one. Summarize the former instead of only ever showing
        // the first song and silently hiding the rest.
        const isBatch = sync.items.length > 1
        const item = sync.items[0]
        const counts = isBatch
          ? sync.items.reduce(
              (acc, i) => {
                if (i.status === 'imported') acc.imported++
                else if (i.status === 'duplicate') acc.duplicate++
                else if (i.status === 'skipped') acc.skipped++
                return acc
              },
              { imported: 0, duplicate: 0, skipped: 0 },
            )
          : null

        return (
          <li key={sync.id} className="history-item">
            <div className="history-main">
              <strong>{sync.source_name}</strong>
              <span className={`status status-${sync.status}`}>{SYNC_STATUS_LABEL[sync.status] ?? sync.status}</span>
            </div>
            {counts ? (
              <div className="history-detail">
                {sync.items.length} canciones — {counts.imported} agregadas, {counts.duplicate} ya existían,{' '}
                {counts.skipped} ignoradas
              </div>
            ) : (
              item?.destination_title && (
                <div className="history-detail">
                  → {item.destination_title} ({item.destination_artist}){' '}
                  {item.status === 'duplicate' && <em>ya existía</em>}
                  {item.confidence != null && <span> · {item.confidence.toFixed(0)}% de confianza</span>}
                </div>
              )
            )}
            <div className="history-meta">
              {sync.destination_name && <span>Playlist: {sync.destination_name} · </span>}
              {formatDate(sync.created_at)}
            </div>
          </li>
        )
      })}
    </ul>
  )
}
