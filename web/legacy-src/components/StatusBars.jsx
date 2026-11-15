import { useEffect, useState } from 'react'
import { useRegisterSW } from 'virtual:pwa-register/react'
import { net, onNet } from '../api.js'
import { useI18n } from '../i18n/index.jsx'

// "Offline: showing data from 14 Nov, 10:32"
export function OfflineBanner() {
  const { t, lang } = useI18n()
  const [online, setOnline] = useState(navigator.onLine)
  const [state, setState] = useState({ ...net })
  useEffect(() => {
    const on = () => setOnline(true)
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    const stop = onNet(setState)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
      stop()
    }
  }, [])
  if (online && !state.failed && !state.cached) return null
  const when = state.dataTime
    ? new Intl.DateTimeFormat(lang === 'mk' ? 'mk-MK' : 'en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
      .format(new Date(state.dataTime))
    : null
  return (
    <div className="banner banner-offline" role="status">
      <span className="dot" aria-hidden="true" />
      {!online ? t('offline.offline') : t('offline.noServer')}
      {when ? ` ${t('offline.showing').replace('{when}', when)}` : ` ${t('offline.nothing')}`}
    </div>
  )
}

// A new version installs in the background; this button reloads into it
export function UpdateButton() {
  const { t } = useI18n()
  const { needRefresh: [needRefresh], updateServiceWorker } = useRegisterSW({
    onRegisteredSW(_url, reg) {
      if (reg) setInterval(() => reg.update(), 60 * 60 * 1000) // check hourly while the app stays open
    },
  })
  if (!needRefresh) return null
  return (
    <button className="btn btn-volt update-btn" onClick={() => updateServiceWorker(true)}>{t('offline.update')}</button>
  )
}
