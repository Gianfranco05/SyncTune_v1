import { ApiError } from './api'

export const SYNC_STATUS_LABEL: Record<string, string> = {
  pending: 'Pendiente',
  analyzing: 'Analizando',
  matching: 'Buscando coincidencias',
  review: 'Sin confirmar',
  importing: 'Importando',
  completed: 'Completada',
  partial: 'Parcial',
  failed: 'Falló',
  cancelled: 'Cancelada',
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' })
}

export const CONFIDENCE_LABEL: Record<string, string> = {
  alta: 'Alta confianza',
  media: 'Confianza media — revisá antes de confirmar',
  baja: 'Confianza baja — puede no ser la canción correcta',
}

export function friendlyError(err: unknown): string {
  // The backend already crafts a specific, correctly-worded message per
  // failure (spec §41) — e.g. "Tu conexión con YouTube expiró..." vs.
  // "...con Spotify...". Never override it with a generic one: on the
  // playlist flow (which needs both providers) that used to tell the user
  // to reconnect the wrong service.
  if (err instanceof ApiError) {
    return err.message
  }
  return 'Ocurrió un error inesperado. Probá de nuevo.'
}
