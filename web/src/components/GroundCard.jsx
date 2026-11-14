import { Line } from 'react-chartjs-2'
import { getSmap, getTerrain, paths } from '../api.js'
import { useI18n } from '../i18n/index.jsx'
import { baseOptions } from './ClimateCharts.jsx'
import useThemeColors from './useThemeColors.js'
import { useData } from './util.js'

// What NASA satellites see at this field: SMAP top-soil moisture against its own normal, and the
// NASADEM slope that sets how fast bare soil washes away. Both say which dataset and which dates.
export default function GroundCard({ fieldId }) {
  const { t } = useI18n()
  const smap = useData(() => getSmap(fieldId), paths.smap(fieldId), [fieldId])
  const ter = useData(() => getTerrain(fieldId), paths.terrain(fieldId), [fieldId])
  const s = smap.data
  const g = ter.data
  if (!s && !g) return null
  const anom = s?.anomaly
  const state = anom == null ? null : anom < -3 ? 'dry' : anom > 3 ? 'wet' : 'ok'
  return (
    <article className="card chart-card ground">
      <div className="card-head">
        <h2>
          <svg className="card-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <path d="M12 3v4M5 7l2 2M19 7l-2 2M4 21l5-8 4 5 3-3 4 6z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {t('ground.title')}
        </h2>
        {state && (
          <span className={`status status-${state}`}><span className="dot" aria-hidden="true" />{t(`ground.state_${state}`)}</span>
        )}
      </div>
      <p className="chart-help">{t('ground.help')}</p>
      <div className="ground-stats">
        {s && (
          <div className="mini-stat">
            <span className="stat-label">{t('ground.smapNow')}</span>
            <span className="mini-value">{s.latest.sm.toFixed(1)}<small>%</small></span>
            <span className="stat-note">
              {s.normal_for_date != null
                ? t('ground.vsNormal').replace('{n}', s.normal_for_date.toFixed(1)).replace('{d}', fmtDay(s.latest.day))
                : t('ground.passed').replace('{d}', fmtDay(s.latest.day))}
            </span>
          </div>
        )}
        {g && (
          <div className="mini-stat">
            <span className="stat-label">{t('ground.slope')}</span>
            <span className="mini-value">{g.slope_deg.toFixed(1)}<small>°</small></span>
            <span className="stat-note">{t(`ground.class_${g.class}`)} · {g.slope_pct}%</span>
          </div>
        )}
        {g && (
          <div className="mini-stat">
            <span className="stat-label">{t('ground.elevation')}</span>
            <span className="mini-value">{g.elevation_m}<small>m</small></span>
            <span className="stat-note">{g.from_outline ? t('ground.outline').replace('{n}', g.pixels) : t('ground.point')}</span>
          </div>
        )}
        {g && (
          <div className="mini-stat">
            <span className="stat-label">{t('ground.erosion')}</span>
            <span className="mini-value">{g.erosion_factor.toFixed(1)}<small>×</small></span>
            <span className="stat-note">{t('ground.erosionNote')}</span>
          </div>
        )}
      </div>
      {s && s.days.length > 10 && <SmapChart s={s} />}
      <p className="source">
        {[s?.source, g?.source].filter(Boolean).map((x) => `${x.dataset} (${x.dates})`).join(' · ')}
      </p>
    </article>
  )
}

function fmtDay(iso) {
  return iso.slice(8, 10) + '.' + iso.slice(5, 7)
}

function SmapChart({ s }) {
  const { t, lang } = useI18n()
  const c = useThemeColors()
  const fmt = new Intl.DateTimeFormat(lang === 'mk' ? 'mk-MK' : 'en-GB', { day: 'numeric', month: 'short' })
  const data = {
    labels: s.days.map((d) => fmt.format(new Date(`${d.day}T12:00:00`))),
    datasets: [
      {
        label: t('ground.normal'), data: s.days.map((d) => d.normal), borderColor: c.smoke, borderDash: [4, 4],
        borderWidth: 1.5, pointRadius: 0, tension: 0.3, spanGaps: true,
      },
      {
        label: t('ground.smap'), data: s.days.map((d) => d.sm), borderColor: c['viz-rain'], backgroundColor: c['viz-rain'],
        borderWidth: 2, pointRadius: 0, pointHoverRadius: 5, tension: 0.25, spanGaps: true,
      },
    ],
  }
  const opts = baseOptions(c, { legend: true, yTitle: t('fc.unit') })
  opts.scales.x.ticks.maxTicksLimit = 7
  opts.scales.x.ticks.autoSkip = true
  opts.plugins.tooltip.callbacks = { label: (i) => `${i.dataset.label}: ${i.parsed.y?.toFixed(1)}%` }
  return <div className="chart chart-sm"><Line data={data} options={opts} /></div>
}
