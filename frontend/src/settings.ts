export type DisplayMode = 'simple' | 'avanzado'
export type SafetyMode = 'seguro' | 'rapido'

export interface SyncSettings {
  displayMode: DisplayMode
  safetyMode: SafetyMode
  // Modo rápido (spec §22): confidence at/above this auto-confirms a
  // single-song sync without an extra click. Never applies to playlists —
  // those are a "big operation" and spec §21 says those always need
  // explicit confirmation regardless of mode.
  fastModeThreshold: number
}

const STORAGE_KEY = 'synctune-settings'

const DEFAULTS: SyncSettings = {
  displayMode: 'avanzado',
  safetyMode: 'seguro',
  fastModeThreshold: 95,
}

export function loadSettings(): SyncSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULTS
    return { ...DEFAULTS, ...JSON.parse(raw) }
  } catch {
    return DEFAULTS
  }
}

export function saveSettings(settings: SyncSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  } catch {
    // Private browsing / storage blocked — settings just won't persist.
  }
}
