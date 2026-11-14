import { useEffect, useState } from 'react'
import { getHealth } from '../api.js'
import { useI18n } from '../i18n/index.jsx'

// Shows whether the Oracle backend answers /health from this device.
export default function ServerStatus() {
  const { t } = useI18n()
  const [state, setState] = useState({ status: 'checking' })

  useEffect(() => {
    let alive = true
    getHealth()
      .then((h) => alive && setState({ status: 'ok', time: h.time }))
      .catch(() => alive && setState({ status: 'down' }))
    return () => {
      alive = false
    }
  }, [])

  return (
    <div className={`card status status-${state.status}`}>
      <span className="label">{t('server.title')}</span>
      <strong>{t(`server.${state.status}`)}</strong>
      {state.time && <span className="muted">{new Date(state.time).toLocaleTimeString()}</span>}
    </div>
  )
}
