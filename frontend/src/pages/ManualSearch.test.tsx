import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ManualSearch from './ManualSearch'

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  searchTracks: vi.fn(),
}))

import { searchTracks } from '../api'

const track = {
  id: 't1',
  uri: 'spotify:track:t1',
  name: 'Blinding Lights',
  artists: 'The Weeknd',
  album: 'After Hours',
  album_image: null,
  external_url: 'https://open.spotify.com/track/t1',
  duration_ms: 200000,
}

describe('ManualSearch', () => {
  beforeEach(() => vi.mocked(searchTracks).mockReset())

  it('searches and hands back the picked track as a manual candidate', async () => {
    vi.mocked(searchTracks).mockResolvedValue([track])
    const onPick = vi.fn()
    const user = userEvent.setup()
    render(<ManualSearch onPick={onPick} />)

    await user.type(screen.getByLabelText(/buscar canción en spotify/i), 'blinding{Enter}')
    await user.click(await screen.findByText('Blinding Lights'))

    expect(searchTracks).toHaveBeenCalledWith('blinding')
    expect(onPick).toHaveBeenCalledWith(expect.objectContaining({ id: 't1', manual: true, confidence: 100 }))
  })

  it('says so when nothing is found', async () => {
    vi.mocked(searchTracks).mockResolvedValue([])
    const user = userEvent.setup()
    render(<ManualSearch onPick={vi.fn()} />)

    await user.type(screen.getByLabelText(/buscar canción en spotify/i), 'zzz{Enter}')

    expect(await screen.findByText(/sin resultados/i)).toBeInTheDocument()
  })
})
