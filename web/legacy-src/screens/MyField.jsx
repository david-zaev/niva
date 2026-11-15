import { lazy, Suspense, useEffect, useState } from 'react'
import { DEMO_FIELD, getField, getLive, paths, peek } from '../api.js'
import Screen from '../components/Screen.jsx'
import SensorTile from '../components/SensorTile.jsx'
import { fieldSoil, soilWater } from '../fieldMeta.js'
import { load, useI18n } from '../i18n/index.jsx'

const FieldMap = lazy(() => import('../components/FieldMap.jsx')) // Leaflet loads after the first numbers

const POLL_MS = 5000
const LIVE_WINDOW_S = 30 // a reading younger than this counts as "live"

function ago(seconds, t) {
  if (seconds < 60) return t('field.agoSeconds').replace('{n}', Math.round(seconds))
  if (seconds < 3600) return t('field.agoMinutes').replace('{n}', Math.round(seconds / 60))
  if (seconds < 86400) return t('field.agoHours').replace('{n}', Math.round(seconds / 3600))
  return t('field.agoDays').replace('{n}', Math.round(seconds / 86400))
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
  const level = soilWater(soil, fieldSoil(fieldId, field))?.level ?? null // dry / good / wet for this field's kind of soil

  const tiles = [
    { key: 'soil', label: t('field.soilMoisture'), value: soil, unit: '%', bar: true,
      level, levelText: level ? t(`field.soil_${level}`) : null },
    { key: 'soilTemp', label: t('field.soilTemp'), value: r?.soil_temp_c ?? null, unit: '°C', digits: 1 },
    { key: 'air', label: t('field.airTemp'), value: r?.air_temp_c ?? null, unit: '°C', digits: 1 },
    { key: 'humidity', label: t('field.humidity'), value: r?.humidity_pct ?? null, unit: '%' },
    { key: 'pressure', label: t('field.pressure'), value: r?.pressure_hpa ?? null, unit: 'hPa', digits: 1 },
  ].map((x) => ({ ...x, badge: x.value != null ? (isLive ? 'live' : ago(age, t)) : null }))

  return (
    <Screen section="field" eyebrow={field ? (fieldId === DEMO_FIELD ? t('field.eyebrow') : field.name) : undefined}>
      <div className="stats">
        {tiles.filter((x) => x.value != null).map(({ key, ...x }) => <SensorTile key={key} {...x} />)}
      </div>
      <Suspense fallback={<p className="card muted">{t('field.loading')}</p>}>
        <FieldMap lat={field?.lat} lon={field?.lon} />
      </Suspense>
    </Screen>
  )
}
