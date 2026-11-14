import { useEffect, useState } from 'react'
import { getForecast, getLive } from '../api.js'
import ForecastChart from '../components/ForecastChart.jsx'
import Screen, { ComingSoon } from '../components/Screen.jsx'
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

function ForecastCard({ fieldId }) {
  const { t } = useI18n()
  const [fc, setFc] = useState(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let alive = true
    const tick = () => getForecast(fieldId).then((d) => alive && (setFc(d), setFailed(false))).catch(() => alive && setFailed(true))
    tick()
    const id = setInterval(tick, 60000) // follows the sensor: the field correction moves with each new reading
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [fieldId])
  if (failed && !fc) return <p className="card muted">{t('fc.notReady')}</p>
  if (!fc) return null
  const input = (x) => {
    const tr = t(`fcInputs.${x}`)
    return tr.startsWith('fcInputs.') ? x : tr
  }
  const fix = fc.field_correction
  return (
    <article className="card chart-card forecast">
      <div className="fc-head">
        <h2>{t('fc.title')}</h2>
        <span className={`pill advice advice-${fc.advice}`}>{t(`fc.advice_${fc.advice}`)}</span>
      </div>
      <p className="chart-help">{t(`fc.help_${fc.advice}`)}</p>
      <div className="fc-legend" aria-hidden="true">
        <span><i className="sw sw-line" />{t('fc.forecast')}</span>
        <span><i className="sw sw-band" />{t('fc.band')}</span>
        <span><i className="sw sw-dry" />{t('fc.dryLine')}</span>
      </div>
      <ForecastChart fc={fc} />
      <dl className="fc-facts">
        <div>
          <dt>{t('fc.error')}</dt>
          <dd>±{fc.error.mae_pct_points.toFixed(1)} {t('fc.points')} <span className="muted">· {t('fc.baseline')} ±{fc.error.no_change_mae.toFixed(1)}</span></dd>
        </div>
        <div>
          <dt>{t('fc.drivers')}</dt>
          <dd>{fc.top_inputs.map(input).join(' · ')}</dd>
        </div>
        <div>
          <dt>{t('fc.fieldFix')}</dt>
          <dd>{fix.applied ? t('fc.fixOn').replace('{n}', `${fix.offset > 0 ? '+' : ''}${fix.offset}`) : t('fc.fixOff')}</dd>
        </div>
      </dl>
      <p className="source">{fc.sources.map((x) => `${x.dataset} (${x.dates})`).join(' · ')} · {t('fc.errorNote')}</p>
    </article>
  )
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
    <Screen section="field">
      <p className="tiles-status">
        <span className={`pill freshness ${isLive ? 'is-live' : ''} ${error ? 'is-down' : ''}`} role="status">
          <span className="dot" aria-hidden="true" />
          {live == null && !error && t('field.loading')}
          {error && t('server.down')}
          {!error && live && !r && t('field.noReadings')}
          {!error && r && (isLive ? t('field.live') : `${t('field.lastReading')} ${ago(age, t)}`)}
        </span>
      </p>

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

      <ForecastCard fieldId={fieldId} />
      <ComingSoon>{t('field.nasaSoon')}</ComingSoon>
    </Screen>
  )
}
