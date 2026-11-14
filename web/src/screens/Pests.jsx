import { useState } from 'react'
import { Link } from 'react-router-dom'
import { addPestReport, deletePestReport, fieldId as currentField, getPests, ownerToken, paths } from '../api.js'
import { ModeToggle, useMode } from '../components/Mode.jsx'
import Screen from '../components/Screen.jsx'
import TermHelp from '../components/TermHelp.jsx'
import { fmt, today, useCrops, useData, useDay } from '../components/util.js'
import { useI18n } from '../i18n/index.jsx'

const LIGHT = { seen: 'bad', high: 'bad', medium: 'dry', low: 'ok', off: 'none' }

function Reason({ r }) {
  const { t } = useI18n()
  if (r.key === 'days') return <li>{fmt(t('pests.r_days'), { n: r.value, of: r.of })} <span className="muted">({r.condition})</span></li>
  if (r.key === 'sensor_humid') return <li>{fmt(t('pests.r_sensorHumid'), { h: Math.round(r.value), t: r.temp })}</li>
  if (r.key === 'sensor_hot_dry') return <li>{fmt(t('pests.r_sensorHot'), { h: Math.round(r.value), t: r.temp })}</li>
  if (r.key === 'pressure_drop') return <li>{fmt(t('pests.r_pressure'), { n: r.value })}</li>
  return <li>{t(`pests.r_${r.key}`)}</li>
}

function RiskCard({ r, spray, advanced }) {
  const { t, lang } = useI18n()
  const { cropName } = useCrops()
  const day = useDay()
  const [open, setOpen] = useState(r.level === 'seen' || r.level === 'high')
  const good = spray.filter((d) => d.ok)
  const needsSpray = r.steps.some((s) => s.type === 'spray')
  return (
    <article className={`card pest-card level-${r.level}`}>
      <div className="card-head">
        <h2><span className={`banner-light light-${LIGHT[r.level]}`} aria-hidden="true" />{lang === 'mk' ? r.name_mk : r.name}</h2>
        <span className={`status status-${LIGHT[r.level]}`}><span className="dot" aria-hidden="true" />{t(`pests.level_${r.level}`)}</span>
      </div>
      <p className="muted small">{r.crops.map(cropName).join(', ')} · {t(`pests.kind_${r.kind}`)}</p>
      <p className="pest-signs"><strong>{t('pests.signs')}:</strong> {lang === 'mk' ? r.signs_mk : r.signs}</p>
      {advanced && r.reasons.length > 0 && <ul className="reasons">{r.reasons.map((x, i) => <Reason key={i} r={x} />)}</ul>}
      {advanced && <p className="source">{t('pests.model')}: {r.model}</p>}
      <button className="link-btn" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? t('pests.hideSteps') : t('pests.showSteps')}</button>
      {open && <ol className="steps">
        {r.steps.map((s, i) => <li key={i} className={`step step-${s.type}`}><span className="pill">{t(`pests.step_${s.type}`)}</span> {lang === 'mk' ? s.mk : s.en}</li>)}
        {needsSpray && <li className="step step-window">
          <span className="pill pill-volt">{t('pests.window')}</span>{' '}
          {good.length ? fmt(t('pests.windowDays'), { days: good.slice(0, 3).map((d) => day(d.day, { weekday: 'long', day: 'numeric' })).join(', ') }) : t('pests.windowNone')}
        </li>}
      </ol>}
    </article>
  )
}

function ReportForm({ fieldId, catalogue, onDone }) {
  const { t, lang } = useI18n()
  const [form, setForm] = useState({ pest: '', seen_on: today(), severity: 'few', note: '' })
  const [msg, setMsg] = useState(null)
  const save = (e) => {
    e.preventDefault()
    addPestReport(fieldId, { ...form, note: form.note || null })
      .then(() => { setMsg({ ok: true }); setForm({ ...form, pest: '', note: '' }); onDone() })
      .catch(() => setMsg({ ok: false }))
  }
  return (
    <form className="card report-form" onSubmit={save}>
      <div className="card-head"><h2>{t('pests.seeTitle')}</h2></div>
      <p className="chart-help">{t('pests.seeHelp')}</p>
      <div className="form-grid">
        <label className="select"><span>{t('pests.what')}</span>
          <select required value={form.pest} onChange={(e) => setForm({ ...form, pest: e.target.value })}>
            <option value="">—</option>
            {catalogue.map((p) => <option key={p.id} value={p.id}>{lang === 'mk' ? p.name_mk : p.name}</option>)}
          </select>
        </label>
        <label className="text-input"><span>{t('pests.when')}</span><input type="date" required max={today()} value={form.seen_on} onChange={(e) => setForm({ ...form, seen_on: e.target.value })} /></label>
        <div className="select"><span>{t('pests.howMany')}</span>
          <div className="segmented">{['few', 'many'].map((v) => <button type="button" key={v} aria-pressed={form.severity === v} onClick={() => setForm({ ...form, severity: v })}>{t(`pests.sev_${v}`)}</button>)}</div>
        </div>
        <label className="text-input wide"><span>{t('crops.notes')}</span><input maxLength={300} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></label>
      </div>
      <button className="btn btn-volt">{t('pests.report')}</button>
      {msg && <p className={`msg ${msg.ok ? 'msg-ok' : 'msg-bad'}`}>{msg.ok ? t('pests.reported') : t('crops.saveFailed')}</p>}
    </form>
  )
}

export default function Pests() {
  const { t, lang } = useI18n()
  const { cropName } = useCrops()
  const day = useDay()
  const fieldId = currentField()
  const owner = ownerToken(fieldId) != null
  const [mode, setMode] = useMode('pests')
  const { data, error, reload } = useData(() => getPests(fieldId), paths.pests(fieldId), [fieldId])
  const advanced = mode === 'advanced'

  if (!data) return <Screen section="pests" actions={<ModeToggle mode={mode} setMode={setMode} />}><p className="card muted">{error ? t('server.down') : t('field.loading')}</p></Screen>
  const shown = data.risks.filter((r) => advanced || r.level !== 'off')
  const resting = data.risks.filter((r) => r.level === 'off').length
  const s = data.sensor

  return (
    <Screen section="pests" actions={<ModeToggle mode={mode} setMode={setMode} />}>
      <p className="note">
        {fmt(t(`pests.cropsFrom_${data.crops_from}`), { crops: data.crops.map(cropName).join(', ') || '—' })}{' '}
        <Link to="/">{t('pests.changeCrops')}</Link>
      </p>

      <div className="spray-strip" aria-label={t('pests.window')}>
        {data.spray.map((d) => (
          <div key={d.day} className={`spray-day ${d.ok ? 'is-ok' : ''}`}>
            <span className="small">{day(d.day, { weekday: 'short' })}</span>
            <strong>{d.ok ? '✓' : '✕'}</strong>
            <span className="muted small">{Math.round(d.wind_kmh)} km/h · {d.rain_mm} mm</span>
          </div>
        ))}
      </div>
      <p className="muted small">{t('pests.sprayRule')} <TermHelp term="sprayWindow" /></p>

      {shown.length === 0 && <p className="card">{t('pests.allQuiet')}</p>}
      <div className="pest-grid">
        {shown.map((r) => <RiskCard key={r.id} r={r} spray={data.spray} advanced={advanced} />)}
      </div>
      {!advanced && resting > 0 && <p className="muted small">{fmt(t('pests.resting'), { n: resting })}</p>}

      {owner
        ? <ReportForm fieldId={fieldId} catalogue={data.catalogue} onDone={reload} />
        : <p className="card muted">{t('pests.ownerOnly')} <Link to="/setup">{t('more.newField')}</Link></p>}

      {data.reports.length > 0 && <article className="card">
        <div className="card-head"><h2>{t('pests.yourReports')}</h2></div>
        <ul className="plain-list">{data.reports.map((r) => {
          const p = data.catalogue.find((c) => c.id === r.pest)
          return (
            <li key={r.id}>
              <span><strong>{p ? (lang === 'mk' ? p.name_mk : p.name) : r.pest}</strong> · {day(r.seen_on)}{r.severity && ` · ${t(`pests.sev_${r.severity}`)}`}{r.note && ` · ${r.note}`}</span>
              {owner && <button className="link-btn" onClick={() => deletePestReport(fieldId, r.id).then(reload)}>✕</button>}
            </li>
          )
        })}</ul>
      </article>}

      {advanced && <article className="card">
        <div className="card-head"><h2>{t('pests.inputsTitle')}</h2></div>
        <p className="chart-help">{t('pests.inputsHelp')}</p>
        <div className="stats sensor-five">
          {[['air', s?.air_temp_c, '°C'], ['humidity', s?.humidity_pct, '%'], ['pressure', s?.pressure_hpa, 'hPa'], ['soil', s?.soil_pct, '%'], ['soilTemp', s?.soil_temp_c, '°C']].map(([k, v, u]) => (
            <div className="card stat" key={k}>
              <span className="stat-label">{t(`pests.sensor_${k}`)}</span>
              <span className="stat-value">{v == null ? '—' : Math.round(v * 10) / 10}<span className="stat-unit">{u}</span></span>
              {k === 'pressure' && data.pressure_change_24h != null && <span className="stat-note">{fmt(t('pests.pressure24'), { n: data.pressure_change_24h > 0 ? `+${data.pressure_change_24h}` : data.pressure_change_24h })}</span>}
            </div>
          ))}
        </div>
        {!s && <p className="muted small">{t('pests.noSensor')}</p>}
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th /><th>Tmin…Tmax °C</th><th>RH %</th><th>{t('metrics.rain')} mm</th><th>GWETTOP</th></tr></thead>
            <tbody>{data.weather_days.map((d) => (
              <tr key={d.day} className={d.day >= today() ? 'is-forecast' : ''}>
                <td>{day(d.day)}{d.day >= today() && <span className="muted small"> · {t('pests.forecastTag')}</span>}</td>
                <td>{Math.round(d.t_min)}…{Math.round(d.t_max)}</td><td>{d.humidity == null ? '—' : Math.round(d.humidity)}</td>
                <td>{d.rain_mm == null ? '—' : Math.round(d.rain_mm * 10) / 10}</td><td>{d.gwettop == null ? '—' : d.gwettop}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </article>}

      <p className="source">{data.sources.map((x) => `${x.dataset} (${x.dates})`).join(' · ')}</p>
    </Screen>
  )
}
