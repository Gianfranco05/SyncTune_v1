import { beforeEach, describe, expect, it } from 'vitest'
import { loadSettings, saveSettings } from './settings'

describe('settings', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('returns sensible defaults when nothing is stored', () => {
    expect(loadSettings()).toEqual({
      displayMode: 'avanzado',
      safetyMode: 'seguro',
      fastModeThreshold: 95,
    })
  })

  it('round-trips a saved value', () => {
    saveSettings({ displayMode: 'simple', safetyMode: 'rapido', fastModeThreshold: 80 })
    expect(loadSettings()).toEqual({
      displayMode: 'simple',
      safetyMode: 'rapido',
      fastModeThreshold: 80,
    })
  })

  it('merges a partial/older stored value with current defaults', () => {
    localStorage.setItem('synctune-settings', JSON.stringify({ displayMode: 'simple' }))
    expect(loadSettings()).toEqual({
      displayMode: 'simple',
      safetyMode: 'seguro',
      fastModeThreshold: 95,
    })
  })

  it('falls back to defaults on corrupt stored JSON instead of throwing', () => {
    localStorage.setItem('synctune-settings', '{not valid json')
    expect(loadSettings()).toEqual({
      displayMode: 'avanzado',
      safetyMode: 'seguro',
      fastModeThreshold: 95,
    })
  })
})
