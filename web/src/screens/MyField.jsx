import { useEffect, useState } from 'react'
import { getLive } from '../api.js'
import Screen from '../components/Screen.jsx'
import SensorTile from '../components/SensorTile.jsx'
import { load, useI18n } from '../i18n/index.jsx'

const POLL_MS = 5000
const LIVE_WINDOW_S = 30 // a reading younger than this counts as "live"

// Rough bands for a capacitive probe after calibration; checked against the plant on day 1
function soilLevel(pct) {
  if (pct < 25) return 'dry'
  if (pct > 70) return 'wet'
  return 'good'
}

function ago(seconds, t) {
  if (seconds < 60) return t('field.agoSeconds').replace('{n}', Math.round(seconds))
  if (seconds < 3600) return t('field.agoMinutes').replace('{n}', Math.round(seconds / 60))
  if (seconds < 86400) return t('field.agoHours').replace('{n}', Math.round(seconds / 3600))
  return t('field.agoDays').replace('{n}', Math.round(seconds / 86400))
}

export default function MyField() {
  const { t } = useI18n()
  const fieldId = load('niva.fieldId', '1')
  const [live, setLive] = useState(null)
  const [error, setError] = useState(false)
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    let alive = true
    const tick = () =>
      getLive(fieldId)
        .then((d) => alive && (setLive(d), setError(false)))
        .catch(() => alive && setError(true))
        .finally(() => alive && setNow(Date.now()))
    tick()
    const id = setInterval(tick, POLL_MS)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [fieldId])

  const r = live?.reading
  const age = r ? (now - new Date(r.time).getTime()) / 1000 : null
  const isLive = age != null && age < LIVE_WINDOW_S && !error

  const soil = r?.soil_pct
  const level = soil != null ? soilLevel(soil) : null

  return (
    <Screen title={t('field.title')}>
      <div className={`card freshness ${isLive ? 'is-live' : ''}`} role="status">
        <span className="dot" aria-hidden="true" />
        {live == null && !error && t('field.loading')}
        {error && t('server.down')}
        {!error && live && !r && t('field.noReadings')}
        {!error && r && (isLive ? t('field.live') : `${t('field.lastReading')} ${ago(age, t)}`)}
      </div>

      {r && (
        <div className="tiles">
          {soil != null && (
            <SensorTile big label={t('field.soilMoisture')} value={soil} unit="%" level={level}
              levelText={t(`field.soil_${level}`)} />
          )}
          {r.soil_temp_c != null && (
            <SensorTile label={t('field.soilTemp')} value={r.soil_temp_c} unit="°C" digits={1} />
          )}
          {r.air_temp_c != null && (
            <SensorTile label={t('field.airTemp')} value={r.air_temp_c} unit="°C" digits={1} />
          )}
          {r.humidity_pct != null && (
            <SensorTile label={t('field.humidity')} value={r.humidity_pct} unit="%" />
          )}
          {r.pressure_hpa != null && (
            <SensorTile label={t('field.pressure')} value={r.pressure_hpa} unit=" hPa" />
          )}
        </div>
      )}

      <p className="card muted">{t('field.nasaSoon')}</p>
    </Screen>
  )
}
