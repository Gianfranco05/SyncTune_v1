import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SongImport from './SongImport'
import type { Sync } from '../types'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  getPlaylists: vi.fn(),
  previewSync: vi.fn(),
  confirmSync: vi.fn(),
  createPlaylist: vi.fn(),
  searchTracks: vi.fn(),
}))

import { confirmSync, getPlaylists, previewSync, searchTracks } from '../api'

function candidate(confidence: number) {
  return {
    id: 't1',
    uri: 'spotify:track:t1',
    name: 'Blinding Lights',
    artists: 'The Weeknd',
    album: 'After Hours',
    album_image: null,
    external_url: 'x',
    duration_ms: 200000,
    confidence,
    confidence_level: confidence >= 90 ? ('alta' as const) : ('media' as const),
  }
}

const synced: Sync = {
  id: 1,
  source: 'youtube',
  destination: 'spotify',
  source_name: 'v',
  destination_name: 'Gym',
  status: 'completed',
  created_at: '2026-09-22T12:00:00Z',
  completed_at: '2026-09-22T12:00:01Z',
  items: [
    {
      id: 1,
      source_title: 'v',
      source_artist: null,
      destination_title: 'Blinding Lights',
      destination_artist: 'The Weeknd',
      status: 'imported',
      confidence: 97,
    },
  ],
}

function setup(confidence: number, settings: object = {}) {
  localStorage.setItem('synctune-settings', JSON.stringify(settings))
  vi.mocked(getPlaylists).mockResolvedValue([{ id: 'p1', name: 'Gym' }])
  vi.mocked(previewSync).mockResolvedValue({
    sync_id: 7,
    video: { video_id: 'v', title: 'The Weeknd - Blinding Lights', channel_title: 'c', duration_ms: 200000 },
    candidates: [candidate(confidence)],
  })
  vi.mocked(confirmSync).mockResolvedValue(synced)
  return userEvent.setup()
}

function renderSong() {
  render(
    <MemoryRouter>
      <SongImport />
    </MemoryRouter>,
  )
}

async function pickPlaylist(user: ReturnType<typeof userEvent.setup>) {
  await waitFor(() => expect(screen.getByRole('option', { name: 'Gym' })).toBeInTheDocument())
  await user.selectOptions(screen.getByDisplayValue(/elegí una playlist/i), 'p1')
}

describe('SongImport', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(confirmSync).mockReset()
    vi.mocked(searchTracks).mockReset()
  })

  it('safe mode (default) waits for the explicit confirm click', async () => {
    const user = setup(97)
    renderSong()
    await user.type(screen.getByPlaceholderText(/url de youtube/i), 'https://youtu.be/abc{Enter}')
    await screen.findByText(/se va a agregar/i)
    await pickPlaylist(user)

    expect(confirmSync).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: /confirmar cambios/i }))

    await waitFor(() => expect(confirmSync).toHaveBeenCalledOnce())
    expect(await screen.findByText(/se agregó a/i)).toBeInTheDocument()
  })

  it('fast mode auto-confirms a high-confidence match once the playlist is picked', async () => {
    const user = setup(97, { safetyMode: 'rapido', fastModeThreshold: 95 })
    renderSong()
    await user.type(screen.getByPlaceholderText(/url de youtube/i), 'https://youtu.be/abc{Enter}')
    await screen.findByText(/se va a agregar/i)
    await pickPlaylist(user)

    await waitFor(() => expect(confirmSync).toHaveBeenCalledOnce())
    expect(vi.mocked(confirmSync).mock.calls[0][0]).toBe(7)
    expect(vi.mocked(confirmSync).mock.calls[0][1]).toMatchObject({ track_id: 't1', confidence: 97, playlist_id: 'p1' })
  })

  it('fast mode still asks for confirmation below the threshold', async () => {
    const user = setup(80, { safetyMode: 'rapido', fastModeThreshold: 95 })
    renderSong()
    await user.type(screen.getByPlaceholderText(/url de youtube/i), 'https://youtu.be/abc{Enter}')
    await screen.findByText(/se va a agregar/i)
    await pickPlaylist(user)

    expect(confirmSync).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /confirmar cambios/i })).toBeInTheDocument()
  })

  it('a hand-picked track never auto-confirms and is sent without a confidence', async () => {
    const user = setup(97, { safetyMode: 'rapido', fastModeThreshold: 95 })
    vi.mocked(searchTracks).mockResolvedValue([
      { ...candidate(0), id: 'm1', uri: 'spotify:track:m1', name: 'Other Song' },
    ])
    renderSong()
    await user.type(screen.getByPlaceholderText(/url de youtube/i), 'https://youtu.be/abc{Enter}')
    await screen.findByText(/se va a agregar/i)

    await user.click(screen.getByRole('button', { name: /buscar manualmente/i }))
    await user.type(screen.getByLabelText(/buscar canción en spotify/i), 'other{Enter}')
    await user.click(await screen.findByRole('button', { name: /other song/i }))
    await pickPlaylist(user)

    expect(confirmSync).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: /confirmar cambios/i }))
    await waitFor(() => expect(confirmSync).toHaveBeenCalledOnce())
    expect(vi.mocked(confirmSync).mock.calls[0][1]).toMatchObject({ track_id: 'm1', confidence: null })
  })
})
