import { useState } from 'react'
import { loadSettings, saveSettings, type SyncSettings } from '../settings'

export default function Settings() {
  const [settings, setSettings] = useState<SyncSettings>(loadSettings)

  function update(patch: Partial<SyncSettings>) {
    const next = { ...settings, ...patch }
    setSettings(next)
    saveSettings(next)
  }

  return (
    <div>
      <h2>Configuración</h2>

      <h3>Modo de interfaz</h3>
      <p className="connections-note">
        Simple oculta el % de confianza y la posibilidad de elegir otro candidato — solo se ve el resultado. Avanzado
        muestra todo, igual que hoy.
      </p>
      <div className="import-mode-switch">
        <button
          className={settings.displayMode === 'simple' ? 'mode-active' : ''}
          onClick={() => update({ displayMode: 'simple' })}
        >
          Simple
        </button>
        <button
          className={settings.displayMode === 'avanzado' ? 'mode-active' : ''}
          onClick={() => update({ displayMode: 'avanzado' })}
        >
          Avanzado
        </button>
      </div>

      <h3>Modo de sincronización</h3>
      <p className="connections-note">
        Seguro (por defecto): siempre pedís confirmación explícita antes de tocar Spotify. Rápido: una canción
        individual con confianza alta se agrega sola, sin ese paso — nunca aplica a playlists, esas siempre piden
        confirmación por ser una operación grande.
      </p>
      <div className="import-mode-switch">
        <button
          className={settings.safetyMode === 'seguro' ? 'mode-active' : ''}
          onClick={() => update({ safetyMode: 'seguro' })}
        >
          Seguro
        </button>
        <button
          className={settings.safetyMode === 'rapido' ? 'mode-active' : ''}
          onClick={() => update({ safetyMode: 'rapido' })}
        >
          Rápido
        </button>
      </div>

      {settings.safetyMode === 'rapido' && (
        <div className="checkbox-inline" style={{ marginTop: '1rem' }}>
          <label htmlFor="threshold">Confianza mínima para auto-confirmar:</label>
          <input
            id="threshold"
            type="number"
            min={70}
            max={100}
            value={settings.fastModeThreshold}
            onChange={(e) => update({ fastModeThreshold: Number(e.target.value) })}
            style={{ width: '4rem' }}
          />
          %
        </div>
      )}
    </div>
  )
}
