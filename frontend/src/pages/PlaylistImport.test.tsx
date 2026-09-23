import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PlaylistImport from './PlaylistImport'
import type { PlaylistPreviewResponse, Sync } from '../types'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  getPlaylists: vi.fn(),
  getYoutubeStatus: vi.fn(),
  previewPlaylist: vi.fn(),
  confirmPlaylist: vi.fn(),
  createPlaylist: vi.fn(),
  searchTracks: vi.fn(),
}))

import { confirmPlaylist, getPlaylists, getYoutubeStatus, previewPlaylist, searchTracks } from '../api'

function track(id: string, name: string, confidence = 95) {
  return {
    id,
    uri: `spotify:track:${id}`,
    name,
    artists: 'Artist',
    album: 'Album',
    album_image: null,
    external_url: 'x',
    duration_ms: 1000,
    confidence,
    confidence_level: 'alta' as const,
  }
}

function batch(offset: number, nextOffset: number | null, total: number): PlaylistPreviewResponse {
  return {
    sync_id: 100 + offset,
    playlist_title: 'Gym Mix',
    total_video_count: total,
    offset,
    next_offset: nextOffset,
    items: [
      {
        item_id: 1,
        video: { video_id: `v${offset}`, title: `Video ${offset}`, channel_title: 'c', duration_ms: 1000 },
        candidates: [track(`t${offset}`, `Song ${offset}`)],
      },
    ],
  }
}

const done: Sync = {
  id: 1,
  source: 'youtube',
  destination: 'spotify',
  source_name: 'Gym Mix',
  destination_name: 'Gym',
  status: 'completed',
  created_at: '2026-09-22T12:00:00Z',
  completed_at: '2026-09-22T12:00:01Z',
  items: [
    { id: 1, source_title: 'v', source_artist: null, destination_title: 's', destination_artist: 'a', status: 'imported', confidence: 90 },
  ],
}

function renderPlaylist() {
  render(
    <MemoryRouter>
      <PlaylistImport />
    </MemoryRouter>,
  )
}

async function loadPreview(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByPlaceholderText(/url de playlist/i), 'https://youtube.com/playlist?list=PL1{Enter}')
  await screen.findByText(/gym mix/i)
}

async function pickDestination(user: ReturnType<typeof userEvent.setup>) {
  await waitFor(() => expect(screen.getByRole('option', { name: 'Gym' })).toBeInTheDocument())
  await user.selectOptions(screen.getByDisplayValue(/playlist destino/i), 'p1')
}

describe('PlaylistImport', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(getYoutubeStatus).mockResolvedValue({ authenticated: true })
    vi.mocked(getPlaylists).mockResolvedValue([{ id: 'p1', name: 'Gym' }])
    vi.mocked(previewPlaylist).mockReset()
    vi.mocked(confirmPlaylist).mockReset().mockResolvedValue(done)
    vi.mocked(searchTracks).mockReset()
  })

  it('asks to connect YouTube instead of showing the form when it is not connected', async () => {
    vi.mocked(getYoutubeStatus).mockResolvedValue({ authenticated: false })
    renderPlaylist()

    expect(await screen.findByText(/necesitás conectar tu cuenta de youtube/i)).toBeInTheDocument()
    expect(screen.queryByPlaceholderText(/url de playlist/i)).not.toBeInTheDocument()
  })

  it('works through a long playlist batch by batch', async () => {
    const user = userEvent.setup()
    vi.mocked(previewPlaylist).mockResolvedValueOnce(batch(0, 50, 120)).mockResolvedValueOnce(batch(50, 100, 120))
    renderPlaylist()
    await loadPreview(user)

    expect(previewPlaylist).toHaveBeenLastCalledWith('https://youtube.com/playlist?list=PL1', 0)
    await pickDestination(user)
    await user.click(screen.getByRole('button', { name: /confirmar cambios/i }))

    await user.click(await screen.findByRole('button', { name: /procesar las siguientes canciones \(51–100 de 120\)/i }))

    await waitFor(() => expect(previewPlaylist).toHaveBeenCalledTimes(2))
    expect(previewPlaylist).toHaveBeenLastCalledWith('https://youtube.com/playlist?list=PL1', 50)
    expect(await screen.findByText(/song 50/i, { exact: false })).toBeInTheDocument()
  })

  it('does not offer a next batch on the last one', async () => {
    const user = userEvent.setup()
    vi.mocked(previewPlaylist).mockResolvedValue(batch(100, null, 120))
    renderPlaylist()
    await loadPreview(user)
    await pickDestination(user)
    await user.click(screen.getByRole('button', { name: /confirmar cambios/i }))

    await screen.findByText(/agregadas/i)
    expect(screen.queryByRole('button', { name: /procesar las siguientes/i })).not.toBeInTheDocument()
  })

  it('lets you pick a track by hand and sends it without a confidence', async () => {
    const user = userEvent.setup()
    vi.mocked(previewPlaylist).mockResolvedValue(batch(0, null, 1))
    vi.mocked(searchTracks).mockResolvedValue([
      { id: 'm1', uri: 'spotify:track:m1', name: 'Manual Pick', artists: 'Artist', album: 'A', album_image: null, external_url: 'x', duration_ms: 1 },
    ])
    renderPlaylist()
    await loadPreview(user)

    await user.click(screen.getByRole('button', { name: /buscar manualmente/i }))
    await user.type(screen.getByLabelText(/buscar canción en spotify/i), 'manual{Enter}')
    await user.click(await screen.findByRole('button', { name: /manual pick/i }))
    await pickDestination(user)
    await user.click(screen.getByRole('button', { name: /confirmar cambios/i }))

    await waitFor(() => expect(confirmPlaylist).toHaveBeenCalledOnce())
    const [, body] = vi.mocked(confirmPlaylist).mock.calls[0]
    expect(body.selections[0]).toMatchObject({ track_id: 'm1', confidence: null, skip: false })
  })
})
