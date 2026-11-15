import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Lines } from './charts.jsx'

const STATUS = { good: 'Good', watch: 'Watch', poor: 'Poor' }

function ago(s) {
  if (s == null) return ''
  if (s < 60) return `${s} s ago`
  if (s < 3600) return `${Math.round(s / 60)} min ago`
  if (s < 86400) return `${Math.round(s / 3600)} h ago`
  return `${Math.round(s / 86400)} days ago`
}

export default function HealthCard({ fieldId, fieldName }) {
  const [live, setLive] = useState(null)
  const [open, setOpen] = useState(false)
  const [err, setErr] = useState(null)
  useEffect(() => {
    let alive = true
    const load = () => api.live(fieldId, 180).then((d) => { if (alive) { setLive(d); setErr(null) } }).catch((e) => alive && setErr(e.message))
    load()
    const t = setInterval(load, 5000)
    return () => { alive = false; clearInterval(t) }
  }, [fieldId])
  const h = live?.health
  const r = live?.reading
  const status = h?.status ?? 'none'
  const fresh = live?.age_s != null && live.age_s < 120 && !live?.reading?.simulated
  return (
    <section className={`card health health-${status}`} aria-live="polite">
      <div className="health-head">
        <div>
          <p className="eyebrow">Soil health · {fieldName} · ESP32 sensor</p>
          <h2 className="health-label">{h?.label ?? (err ? 'Sensor unreachable' : 'Loading…')}</h2>
          <p className="health-summary">{h?.summary ?? err}</p>
        </div>
        <div className={`live-dot ${fresh ? 'is-live' : ''}`}>
          <span className="dot" />{r ? (r.simulated ? 'Simulated readings' : fresh ? 'Live' : `Last reading ${ago(live.age_s)}`) : 'No readings'}
        </div>
      </div>

      {r && (
        <div className="readings">
          <div><span>Soil moisture</span><b>{r.soil_pct ?? '–'}<small>%</small></b></div>
          <div><span>Soil temp</span><b>{r.soil_temp_c ?? '–'}<small>°C</small></b></div>
          <div><span>Air temp</span><b>{r.air_temp_c ?? '–'}<small>°C</small></b></div>
          <div><span>Humidity</span><b>{r.humidity_pct ?? '–'}<small>%</small></b></div>
          <div><span>Pressure</span><b>{r.pressure_hpa ?? '–'}<small>hPa</small></b></div>
        </div>
      )}

      {live?.alerts?.length > 0 && (
        <ul className="alerts">
          {live.alerts.map((a) => (
            <li key={a.id} className={`alert alert-${a.level}`}>
              <b>{a.title}</b> {a.text}
            </li>
          ))}
        </ul>
      )}

      <button className="read-more" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? 'Show less' : 'Read more: why'}
      </button>

      {open && (
        <div className="health-more">
          {h?.items?.length ? (
            <ul className="checks">
              {h.items.map((i) => (
                <li key={i.id} className={`check check-${i.status}`}>
                  <div className="check-top">
                    <span className={`pill pill-${i.status}`}>{STATUS[i.status]}</span>
                    <b>{i.title}</b>
                    <span className="check-value">{i.value}</span>
                  </div>
                  <p>{i.text}</p>
                  <p className="muted small">{i.why}</p>
                </li>
              ))}
            </ul>
          ) : <p className="muted">No sensor readings for this field yet.</p>}
          {h?.soil_basis && <p className="muted small">Soil used to read the sensor: {h.soil_basis}.</p>}
          {live?.series?.length > 3 && (
            <Lines label="Soil moisture, last 3 hours" height={160} yMax={100} yUnit="%"
              xFormat={(v) => new Date(v).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              lines={[
                { name: 'Soil moisture', color: 'var(--series-1)', points: live.series.filter((s) => s.soil_pct != null).map((s) => ({ x: Date.parse(s.time), y: s.soil_pct })) },
                ...(live.series.some((s) => s.soil2_pct != null)
                  ? [{ name: 'Probe 2 (covered pot)', color: 'var(--series-2)', points: live.series.filter((s) => s.soil2_pct != null).map((s) => ({ x: Date.parse(s.time), y: s.soil2_pct })) }]
                  : []),
              ]} />
          )}
        </div>
      )}
    </section>
  )
}
