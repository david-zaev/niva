import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { useI18n } from '../i18n/index.jsx'
import { Lines } from './charts.jsx'
import Toggle from './Toggle.jsx'
import { sensorStatus } from '../sensorStatus.js'

export default function HealthCard({ fieldId, fieldName }) {
  const { t, lang } = useI18n()
  const [snapshot, setSnapshot] = useState(null)
  const [now, setNow] = useState(Date.now)
  const [open, setOpen] = useState(false)
  const [failure, setFailure] = useState(null)
  const err = failure?.fieldId === fieldId && failure?.lang === lang ? failure.message : null
  useEffect(() => {
    let alive = true
    let poll
    let controller
    const load = async () => {
      controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 10000)
      try {
        const data = await api.live(fieldId, 180, lang, controller.signal)
        if (alive) {
          const receivedAt = Date.now()
          setSnapshot({ data, receivedAt, fieldId, lang })
          setNow(receivedAt)
          setFailure(null)
        }
      } catch (e) {
        if (alive) setFailure({ fieldId, lang, message: e.message })
      } finally {
        clearTimeout(timeout)
        if (alive) poll = setTimeout(load, 5000)
      }
    }
    load()
    // Age must advance even when the server stops answering.
    const clock = setInterval(() => setNow(Date.now()), 1000)
    return () => { alive = false; clearTimeout(poll); clearInterval(clock); controller.abort() }
  }, [fieldId, lang])
  const ago = (s) => {
    if (s == null) return ''
    if (s < 60) return t('app.health.agoS', { n: s })
    if (s < 3600) return t('app.health.agoM', { n: Math.round(s / 60) })
    if (s < 86400) return t('app.health.agoH', { n: Math.round(s / 3600) })
    return t('app.health.agoD', { n: Math.round(s / 86400) })
  }
  const current = snapshot?.fieldId === fieldId && snapshot?.lang === lang ? snapshot : null
  const live = current?.data
  const { age, fresh } = sensorStatus(current, now, !!err)
  const h = live?.health
  const r = live?.reading
  const offline = r && !r.simulated && !fresh
  const status = fresh ? h?.status ?? 'none' : 'none'
  const state = err ? t('app.health.unreachable') : r ? (r.simulated ? t('app.health.simulated') : fresh ? t('app.health.live') : t('app.health.offline')) : t('app.health.none')
  const label = err ? t('app.health.unreachable') : offline ? t('app.health.offline') : h?.label ?? t('app.health.loading')
  const summary = err ? t('app.health.serverDown') : offline ? t('app.health.offlineSummary') : h?.summary
  return (
    <section className={`card health health-${status}`} aria-live="polite">
      <div className="health-head">
        <div>
          <p className="eyebrow">{t('app.health.eyebrow', { field: fieldName })}</p>
          <h2 className="health-label">{label}</h2>
          <p className="health-summary">{summary}</p>
        </div>
        <div className={`live-dot ${fresh ? 'is-live' : ''}`}><span className="dot" />{state}</div>
      </div>

      {r && !fresh && <p className="muted small">{r.simulated ? t('app.health.simulated') : age == null ? t('app.health.lastUnknown') : t('app.health.last', { ago: ago(age) })}</p>}
      {r && (
        <div className="readings">
          <div><span>{t('app.health.soil')}</span><b>{r.soil_pct ?? '–'}<small>%</small></b></div>
          <div><span>{t('app.health.soilTemp')}</span><b>{r.soil_temp_c ?? '–'}<small>°C</small></b></div>
          <div><span>{t('app.health.air')}</span><b>{r.air_temp_c ?? '–'}<small>°C</small></b></div>
          <div><span>{t('app.health.humidity')}</span><b>{r.humidity_pct ?? '–'}<small>%</small></b></div>
          <div><span>{t('app.health.pressure')}</span><b>{r.pressure_hpa ?? '–'}<small>hPa</small></b></div>
        </div>
      )}

      {fresh && live?.alerts?.length > 0 && (
        <ul className="alerts">
          {live.alerts.map((a) => (
            <li key={a.id} className={`alert alert-${a.level}`}><b>{a.title}</b> {a.text}</li>
          ))}
        </ul>
      )}

      <Toggle open={open} onClick={() => setOpen(!open)} more={t('app.health.more')} less={t('app.health.less')} />

      {open && (
        <div className="health-more">
          {r && !fresh && <p className="muted">{t('app.health.historical')}</p>}
          {h?.items?.length ? (
            <ul className="checks">
              {h.items.map((i) => (
                <li key={i.id} className={`check check-${i.status}`}>
                  <div className="check-top">
                    <span className={`pill pill-${i.status}`}>{t(`app.health.${i.status}`)}</span>
                    <b>{i.title}</b>
                    <span className="check-value">{i.value}</span>
                  </div>
                  <p>{i.text}</p>
                  <p className="muted small">{i.why}</p>
                </li>
              ))}
            </ul>
          ) : <p className="muted">{t('app.health.noReadings')}</p>}
          {h?.soil_basis && <p className="muted small">{t('app.health.basis', { soil: h.soil_basis })}</p>}
          {live?.series?.length > 3 && (
            <Lines label={t('app.health.chart')} height={160} yMax={100} yUnit="%"
              xFormat={(v) => new Date(v).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              lines={[
                { name: t('app.health.soil'), color: 'var(--series-1)', points: live.series.filter((s) => s.soil_pct != null).map((s) => ({ x: Date.parse(s.time), y: s.soil_pct })) },
                ...(live.series.some((s) => s.soil2_pct != null)
                  ? [{ name: t('app.health.probe2'), color: 'var(--series-2)', points: live.series.filter((s) => s.soil2_pct != null).map((s) => ({ x: Date.parse(s.time), y: s.soil2_pct })) }]
                  : []),
              ]} />
          )}
        </div>
      )}
    </section>
  )
}
