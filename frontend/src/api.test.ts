import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, createPlaylist, getSpotifyMe } from './api'

function mockFetchOnce(response: { ok: boolean; status: number; json: () => Promise<unknown> }) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('api request()', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends credentials and JSON headers, and returns the parsed body on success', async () => {
    const fetchMock = mockFetchOnce({
      ok: true,
      status: 200,
      json: async () => ({ authenticated: true, id: 'user1', display_name: 'Gian' }),
    })

    const result = await getSpotifyMe()

    expect(result).toEqual({ authenticated: true, id: 'user1', display_name: 'Gian' })
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toContain('/api/spotify/me')
    expect(options.credentials).toBe('include')
    expect(options.headers['Content-Type']).toBe('application/json')
  })

  it('serializes the request body as JSON for a POST', async () => {
    const fetchMock = mockFetchOnce({
      ok: true,
      status: 201,
      json: async () => ({ id: 'p1', name: 'Gym' }),
    })

    await createPlaylist('Gym')

    const [, options] = fetchMock.mock.calls[0]
    expect(options.method).toBe('POST')
    expect(JSON.parse(options.body)).toEqual({ name: 'Gym' })
  })

  it('throws an ApiError with the backend-provided detail on a non-ok JSON response', async () => {
    mockFetchOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'No autenticado con Spotify' }),
    })

    await expect(getSpotifyMe()).rejects.toMatchObject(
      new ApiError(401, 'No autenticado con Spotify'),
    )
  })

  it('falls back to a generic message when the error response has no JSON body', async () => {
    mockFetchOnce({
      ok: false,
      status: 502,
      json: async () => {
        throw new Error('not json')
      },
    })

    await expect(getSpotifyMe()).rejects.toMatchObject(new ApiError(502, 'Ocurrió un error inesperado.'))
  })
})
