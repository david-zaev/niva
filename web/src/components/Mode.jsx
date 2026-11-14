import { useState } from 'react'
import { load, save, useI18n } from '../i18n/index.jsx'

// Simple (default) or Advanced, remembered separately for every page. Both views use the same answer from the
// server, so Advanced only adds the numbers behind what Simple says.
export function useMode(page) {
  const [mode, setModeState] = useState(() => load(`niva.mode.${page}`, 'simple'))
  const setMode = (m) => {
    setModeState(m)
    save(`niva.mode.${page}`, m)
  }
  return [mode, setMode]
}

export function ModeToggle({ mode, setMode }) {
  const { t } = useI18n()
  return (
    <div className="segmented mode-toggle" role="group" aria-label={t('mode.label')}>
      <button aria-pressed={mode === 'simple'} onClick={() => setMode('simple')}>{t('mode.simple')}</button>
      <button aria-pressed={mode === 'advanced'} onClick={() => setMode('advanced')}>{t('mode.advanced')}</button>
    </div>
  )
}
