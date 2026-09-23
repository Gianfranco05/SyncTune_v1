import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import CommandPalette, { type PaletteAction } from './CommandPalette'

function makeActions(): PaletteAction[] {
  return [
    { id: 'dashboard', label: 'Ir a Dashboard', run: vi.fn() },
    { id: 'song', label: 'Importar canción', run: vi.fn() },
    { id: 'history', label: 'Ver historial', run: vi.fn() },
  ]
}

describe('CommandPalette', () => {
  it('filters actions as the user types', async () => {
    const user = userEvent.setup()
    const actions = makeActions()
    render(<CommandPalette actions={actions} onClose={vi.fn()} />)

    await user.type(screen.getByPlaceholderText(/buscar acción/i), 'historial')

    expect(screen.getByText('Ver historial')).toBeInTheDocument()
    expect(screen.queryByText('Ir a Dashboard')).not.toBeInTheDocument()
    expect(screen.queryByText('Importar canción')).not.toBeInTheDocument()
  })

  it('shows "Sin resultados" when nothing matches', async () => {
    const user = userEvent.setup()
    render(<CommandPalette actions={makeActions()} onClose={vi.fn()} />)

    await user.type(screen.getByPlaceholderText(/buscar acción/i), 'zzz no existe')

    expect(screen.getByText(/sin resultados/i)).toBeInTheDocument()
  })

  it('runs the first filtered action and closes on Enter', async () => {
    const user = userEvent.setup()
    const actions = makeActions()
    const onClose = vi.fn()
    render(<CommandPalette actions={actions} onClose={onClose} />)

    await user.type(screen.getByPlaceholderText(/buscar acción/i), 'historial{Enter}')

    expect(actions[2].run).toHaveBeenCalledOnce()
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('runs the clicked action and closes', async () => {
    const user = userEvent.setup()
    const actions = makeActions()
    const onClose = vi.fn()
    render(<CommandPalette actions={actions} onClose={onClose} />)

    await user.click(screen.getByText('Importar canción'))

    expect(actions[1].run).toHaveBeenCalledOnce()
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('closes without running anything on Escape', async () => {
    const user = userEvent.setup()
    const actions = makeActions()
    const onClose = vi.fn()
    render(<CommandPalette actions={actions} onClose={onClose} />)

    await user.type(screen.getByPlaceholderText(/buscar acción/i), '{Escape}')

    expect(onClose).toHaveBeenCalledOnce()
    for (const action of actions) {
      expect(action.run).not.toHaveBeenCalled()
    }
  })

  it('closes when clicking the overlay outside the palette', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    const { container } = render(<CommandPalette actions={makeActions()} onClose={onClose} />)

    await user.click(container.querySelector('.palette-overlay')!)

    expect(onClose).toHaveBeenCalledOnce()
  })
})
