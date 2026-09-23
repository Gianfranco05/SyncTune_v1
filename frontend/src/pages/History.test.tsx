import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import History from './History'
import type { Sync } from '../types'

vi.mock('../api', () => ({
  getSyncHistory: vi.fn(),
}))

import { getSyncHistory } from '../api'

function makeSync(overrides: Partial<Sync> = {}): Sync {
  return {
    id: 1,
    source: 'youtube',
    destination: 'spotify',
    source_name: 'Blinding Lights',
    destination_name: 'My Playlist',
    status: 'completed',
    created_at: '2026-09-22T12:00:00Z',
    completed_at: '2026-09-22T12:01:00Z',
    items: [
      {
        id: 1,
        source_title: 'Blinding Lights',
        source_artist: null,
        destination_title: 'Blinding Lights',
        destination_artist: 'The Weeknd',
        status: 'imported',
        confidence: 96,
      },
    ],
    ...overrides,
  }
}

describe('History', () => {
  it('shows an empty state with no syncs', async () => {
    vi.mocked(getSyncHistory).mockResolvedValue([])

    render(<History />)

    expect(await screen.findByText(/todavía no sincronizaste/i)).toBeInTheDocument()
  })

  it('shows a friendly error if the history fails to load', async () => {
    vi.mocked(getSyncHistory).mockRejectedValue(new Error('network down'))

    render(<History />)

    expect(await screen.findByText(/no pudimos cargar el historial/i)).toBeInTheDocument()
  })

  it('shows per-track detail for a single-song sync', async () => {
    vi.mocked(getSyncHistory).mockResolvedValue([makeSync()])

    render(<History />)

    await waitFor(() => expect(screen.getByText('Blinding Lights')).toBeInTheDocument())
    expect(screen.getByText(/The Weeknd/)).toBeInTheDocument()
    expect(screen.getByText(/96% de confianza/)).toBeInTheDocument()
  })

  it('shows a batch summary instead of just the first song for a playlist sync', async () => {
    // Regression: this used to only ever render items[0], silently hiding
    // the other (up to 49) songs a playlist sync processed.
    const playlistSync = makeSync({
      source_name: 'Gym Playlist',
      items: [
        { id: 1, source_title: 'A', source_artist: null, destination_title: 'A', destination_artist: 'X', status: 'imported', confidence: 90 },
        { id: 2, source_title: 'B', source_artist: null, destination_title: 'B', destination_artist: 'X', status: 'duplicate', confidence: 88 },
        { id: 3, source_title: 'C', source_artist: null, destination_title: null, destination_artist: null, status: 'skipped', confidence: null },
      ],
    })
    vi.mocked(getSyncHistory).mockResolvedValue([playlistSync])

    render(<History />)

    expect(await screen.findByText(/3 canciones — 1 agregadas, 1 ya existían, 1 ignoradas/)).toBeInTheDocument()
    // And NOT just song "A" in isolation the way the single-song view would render it.
    expect(screen.queryByText(/^→ A/)).not.toBeInTheDocument()
  })
})
