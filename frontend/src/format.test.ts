import { describe, expect, it } from 'vitest'
import { ApiError } from './api'
import { formatDate, friendlyError } from './format'

describe('friendlyError', () => {
  it('uses the backend-provided message for an ApiError, unmodified', () => {
    // Regression: this used to be overridden with a hardcoded "Tu conexión
    // con Spotify expiró" for any 401, which was wrong whenever the actual
    // failure was with YouTube (the playlist flow needs both providers).
    const err = new ApiError(401, 'Tu conexión con YouTube expiró. Reconectá tu cuenta para seguir.')
    expect(friendlyError(err)).toBe('Tu conexión con YouTube expiró. Reconectá tu cuenta para seguir.')
  })

  it('passes through a non-401 ApiError message as-is', () => {
    const err = new ApiError(502, 'Uno de los servicios externos no respondió correctamente. Probá de nuevo.')
    expect(friendlyError(err)).toBe('Uno de los servicios externos no respondió correctamente. Probá de nuevo.')
  })

  it('falls back to a generic message for a non-ApiError', () => {
    expect(friendlyError(new TypeError('boom'))).toBe('Ocurrió un error inesperado. Probá de nuevo.')
    expect(friendlyError('plain string')).toBe('Ocurrió un error inesperado. Probá de nuevo.')
    expect(friendlyError(undefined)).toBe('Ocurrió un error inesperado. Probá de nuevo.')
  })
})

describe('formatDate', () => {
  it('formats an ISO timestamp without throwing', () => {
    const result = formatDate('2026-09-22T15:30:00Z')
    expect(typeof result).toBe('string')
    expect(result.length).toBeGreaterThan(0)
  })
})
