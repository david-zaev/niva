import { Link } from 'react-router-dom'
import { useI18n } from '../i18n/index.jsx'
import { fmt, useCrops, useDay } from './util.js'

const ICON = {
  soil: 'M3 17h18M5 13c2-3 4-4 7-4s5 1 7 4M12 9V4m-3 2 3-2 3 2',
  crop: 'M12 21V9m0 0c0-3 2-6 6-6 0 4-3 6-6 6Zm0 4c0-3-2-5-6-5 0 3 3 5 6 5Z',
  next: 'M4 14a5 5 0 0 1 9-3 4 4 0 1 1 3 7H7a3 3 0 0 1-3-4Zm4 6-1 2m5-2-1 2m5-2-1 2',
  pest: 'M12 7a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0v-5a3 3 0 0 1 3-3Zm0-4v4M5 9l4 2m10-2-4 2M5 17l4-2m10 2-4-2',
}
const LIGHT = { ok: 'ok', dry: 'dry', wet: 'wet', unknown: 'none', ready: 'dry', soon: 'ok', growing: 'ok',
  high: 'bad', medium: 'dry', seen: 'bad', low: 'ok' }

function Row({ icon, light, title, children, action }) {
  return (
    <div className="banner-row">
      <span className={`banner-light light-${light}`} aria-hidden="true">
        <svg viewBox="0 0 24 24" width="18" height="18"><path d={ICON[icon]} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </span>
      <div className="banner-text">
        <strong>{title}</strong>
        <p>{children}</p>
      </div>
      {action}
    </div>
  )
}

export default function SummaryBanner({ s, onHarvest, owner }) {
  const { t, lang } = useI18n()
  const { cropName } = useCrops()
  const day = useDay()
  const r = s.readiness
  const pct = (v) => (v == null ? '—' : `${Math.round(v * 100)}%`)
  const temp = r.soil_temp_c ?? r.air_temp_7d
  const warmth = temp == null ? '' : fmt(t(r.temp_source === 'sensor' ? 'summary.soilTemp' : 'summary.airTemp'), { n: temp })
  const soilText = r.status === 'unknown' ? t('summary.soilUnknown')
    : fmt(t(`summary.soil_${r.status}`), { top: pct(r.gwettop), root: pct(r.gwetroot) }) + (r.soil_pct != null ? ` ${fmt(t('summary.sensorSays'), { n: Math.round(r.soil_pct) })}` : '')
  const sow = r.sow_now.map((x) => fmt(t(x.warm_enough && r.status === 'ok' ? 'summary.sowGo' : x.warm_enough ? 'summary.sowSoil' : 'summary.sowCold'), { crop: cropName(x.crop) }))
  const n = s.next
  const soilFc = s.soil_next?.advice

  return (
    <section className="card banner" aria-label={t('summary.title')}>
      <div className="card-head"><h2>{t('summary.title')}</h2><span className="muted small">{s.name}</span></div>

      <Row icon="soil" light={LIGHT[r.status]} title={t(`summary.soilTitle_${r.status}`)}>
        {soilText} {warmth} {sow.join(' ')}
      </Row>

      {s.crops.length === 0
        ? <Row icon="crop" light="none" title={t('summary.noCropsTitle')}>
            {t(owner ? 'summary.noCrops' : 'summary.noCropsDemo')}
          </Row>
        : s.crops.map((c) => (
          <Row key={c.id} icon="crop" light={LIGHT[c.status] ?? 'none'}
            title={fmt(t(`summary.crop_${c.status}`), { crop: cropName(c.crop) })}
            action={c.status === 'ready' || c.status === 'soon'
              ? owner && <button className="btn btn-volt" onClick={() => onHarvest?.(c)}>{t('summary.enterHarvest')}</button>
              : null}>
            {c.progress != null
              ? fmt(t('summary.cropProgress'), { gdd: c.gdd, need: c.gdd_needed, pct: Math.min(999, Math.round(c.progress * 100)), date: day(c.expected_harvest, { day: 'numeric', month: 'long' }) })
              : t('summary.cropNoModel')}
          </Row>
        ))}

      {n && <Row icon="next" light={n.frost_days.length || n.hot_days.length ? 'dry' : 'ok'} title={t('summary.nextTitle')}>
        {n.rain_total >= 1
          ? fmt(t('summary.rainComing'), { mm: n.rain_total, day: day(n.wettest_day, { weekday: 'long' }), max: n.wettest_mm })
          : t('summary.noRain')}{' '}
        {fmt(t('summary.temps'), { max: Math.round(n.t_max), min: Math.round(n.t_min) })}{' '}
        {n.frost_days.length > 0 && fmt(t('summary.frost'), { day: day(n.frost_days[0], { weekday: 'long' }) }) + ' '}
        {n.hot_days.length > 0 && fmt(t('summary.heat'), { day: day(n.hot_days[0], { weekday: 'long' }) }) + ' '}
        {soilFc && t(`summary.water_${soilFc}`)}{' '}
        {n.humid_after_rain && t('summary.fungal')}
      </Row>}

      <Row icon="pest" light={s.pests[0] ? LIGHT[s.pests[0].level] : 'ok'} title={t('summary.pestTitle')}
        action={<Link className="btn btn-ghost" to="/pests">{t('summary.pestOpen')}</Link>}>
        {s.pests.length
          ? s.pests.map((p) => `${lang === 'mk' ? p.name_mk : p.name} (${t(`pests.level_${p.level}`)})`).join(', ')
          : t('summary.pestNone')}
      </Row>

      <p className="source">{s.sources.map((x) => `${x.dataset} (${x.dates})`).join(' · ')}</p>
    </section>
  )
}
