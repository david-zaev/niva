import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { DEMO_FIELD, forget, getField, getForecast, getLive, getSummary, ownerToken, paths, peek } from '../api.js'
import CropTracker from '../components/CropTracker.jsx'
import FieldMetrics from '../components/FieldMetrics.jsx'
import ForecastChart from '../components/ForecastChart.jsx'
import { ModeToggle, useMode } from '../components/Mode.jsx'
import SummaryBanner from '../components/SummaryBanner.jsx'
import { useData } from '../components/util.js'
import Screen from '../components/Screen.jsx'
import SensorTile from '../components/SensorTile.jsx'
import TermHelp from '../components/TermHelp.jsx'
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
  const [fc, setFc] = useState(() => peek(paths.forecast(fieldId)))
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
  const fix = fc.field_correction
  return (
    <article className="card chart-card">
      <div className="card-head">
        <h2><Icon d="M4 14c3-6 5-9 8-9s5 3 8 9M4 19h16" />{t('fc.title')}</h2>
        <span className={`status status-${fc.advice}`}><span className="dot" aria-hidden="true" />{t(`fc.advice_${fc.advice}`)}</span>
      </div>
      <p className="chart-help">{t(`fc.help_${fc.advice}`)}</p>
      <div className="legend" aria-hidden="true">
        <span><i className="sw sw-line" />{t('fc.forecast')}</span>
        <span><i className="sw sw-band" />{t('fc.band')}</span>
        <span><i className="sw sw-dry" />{t('fc.dryLine')}</span>
      </div>
      <ForecastChart fc={fc} />
      <p className="card-foot">
        {t('fc.usuallyOff').replace('{n}', fc.error.mae_pct_points.toFixed(1))} <TermHelp term="forecastError" />
        {fix.applied && <> · {t('fc.fixOn').replace('{n}', `${fix.offset > 0 ? '+' : ''}${fix.offset}`)}</>}
      </p>
      <p className="source">{fc.sources.map((x) => `${x.dataset} (${x.dates})`).join(' · ')}</p>
    </article>
  )
}

export function Icon({ d }) {
  return (
    <svg className="card-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
      <path d={d} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export default function MyField() {
  const { t } = useI18n()
  const fieldId = load('niva.fieldId', '1')
  const [live, setLive] = useState(() => peek(paths.live(fieldId)))
  const [error, setError] = useState(false)
  const [now, setNow] = useState(Date.now())
  const [field, setField] = useState(() => peek(paths.field(fieldId)))
  useEffect(() => {
    getField(fieldId).then(setField).catch(() => {})
  }, [fieldId])

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
  const soil = r?.soil_pct ?? null
  const level = soil != null ? soilLevel(soil) : null
  const isDemo = fieldId === DEMO_FIELD
  const owner = ownerToken(fieldId) != null
  const [mode, setMode] = useMode('field')
  const summary = useData(() => getSummary(fieldId), paths.summary(fieldId), [fieldId])
  const [harvestFor, setHarvestFor] = useState(null)
  const refresh = () => { forget(fieldId); summary.reload() }

  const actions = (
    <>
      <span className={`chip freshness ${isLive ? 'is-live' : ''} ${error ? 'is-down' : ''}`} role="status">
        <span className="dot" aria-hidden="true" />
        {live == null && !error && t('field.loading')}
        {error && t('server.down')}
        {!error && live && !r && t('field.noSensor')}
        {!error && r && (isLive ? t('field.live') : `${t('field.lastReading')} ${ago(age, t)}`)}
      </span>
      {isDemo && !owner && <Link className="btn btn-volt" to="/setup">{t('more.newField')}</Link>}
      <ModeToggle mode={mode} setMode={setMode} />
    </>
  )

  return (
    <Screen section="field" eyebrow={field ? (isDemo ? t('field.eyebrow') : field.name) : undefined} actions={actions}>
      {summary.data
        ? <SummaryBanner s={summary.data} owner={owner} onHarvest={(c) => setHarvestFor({ ...c })} />
        : <p className="card muted">{summary.error ? t('server.down') : t('summary.loading')}</p>}
      <div className="stats">
        <SensorTile label={t('field.soilMoisture')} value={soil} unit="%" level={level} bar
          levelText={level ? t(`field.soil_${level}`) : null} />
        <SensorTile label={t('field.soilTemp')} value={r?.soil_temp_c ?? null} unit="°C" digits={1} />
        <SensorTile label={t('field.airTemp')} value={r?.air_temp_c ?? null} unit="°C" digits={1} />
        <SensorTile label={t('field.humidity')} value={r?.humidity_pct ?? null} unit="%" />
      </div>
      <ForecastCard fieldId={fieldId} />
      <CropTracker fieldId={fieldId} owner={owner} harvestFor={harvestFor} onChange={refresh} />
      {mode === 'advanced' && <FieldMetrics fieldId={fieldId} />}
    </Screen>
  )
}
