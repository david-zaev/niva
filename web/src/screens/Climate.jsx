import { useEffect, useState } from 'react'
import { getClimate, paths, peek } from '../api.js'
import { FrostChart, HeatDaysChart, WaterBalanceChart } from '../components/ClimateCharts.jsx'
import { ModeToggle, useMode } from '../components/Mode.jsx'
import Screen from '../components/Screen.jsx'
import TermHelp from '../components/TermHelp.jsx'
import { load, useI18n } from '../i18n/index.jsx'
import { Icon } from './MyField.jsx'

const sign = (v) => (v > 0 ? `+${v}` : `${v}`)

function Stat({ label, value, unit, note }) {
  return (
    <div className="card stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}<span className="stat-unit">{unit}</span></span>
      <span className="stat-note">{note}</span>
    </div>
  )
}

const ICONS = {
  et0: 'M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11Z',
  heatDays: 'M12 3v2m0 14v2M3 12h2m14 0h2M5.6 5.6 7 7m10 10 1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z',
  frostFree: 'M12 2v20M4 6l16 12M20 6 4 18',
}

function ChartCard({ title, term, help, source, children }) {
  return (
    <div className="card chart-card">
      <div className="card-head"><h2>{term && <Icon d={ICONS[term]} />}{title}{term && <TermHelp term={term} />}</h2></div>
      {help && <p className="chart-help">{help}</p>}
      {children}
      <p className="source">{source}</p>
    </div>
  )
}

export default function Climate() {
  const { t, lang } = useI18n()
  const fieldId = load('niva.fieldId', '1')
  const [d, setD] = useState(() => peek(paths.climate(fieldId)))
  const [error, setError] = useState(false)
  const [historical, setHistorical] = useState(false)
  const [mode, setMode] = useMode('climate')
  const toggle = <ModeToggle mode={mode} setMode={setMode} />

  useEffect(() => {
    const refresh = () => getClimate(fieldId).then((data) => { setD(data); setError(false) }).catch(() => setError(true))
    refresh()
    const timer = setInterval(refresh, 15 * 60 * 1000)
    window.addEventListener('focus', refresh)
    return () => { clearInterval(timer); window.removeEventListener('focus', refresh) }
  }, [fieldId])

  if (error && !d) return <Screen section="climate" actions={toggle}><p className="card">{t('server.down')}</p></Screen>
  if (!d) return <Screen section="climate" actions={toggle}><p className="card muted">{t('field.loading')}</p></Screen>

  const src = d.sources[0]
  const base = d.periods.baseline
  const recent = d.periods.recent
  const current = d.current
  const showCurrent = current && !historical
  const date = (value) => value ? new Intl.DateTimeFormat(lang === 'mk' ? 'mk-MK' : 'en-GB', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T12:00:00`)) : '—'
  const currentLabel = current ? `${current.year} ${t(current.partial ? 'climate.soFar' : 'climate.observed')}` : ''
  const yearly = current && !d.yearly.some((row) => row.year === current.year) ? [...d.yearly, current] : d.yearly
  const source = (period) => `${src.dataset} · ${period} · ${d.location.name} (${d.location.lat}, ${d.location.lon})`
  const deficit = d.monthly.recent.filter((m) => m.balance_mm < 0)
  const deficitTotal = Math.round(deficit.reduce((s, m) => s + m.balance_mm, 0))

  return (
    <Screen section="climate" actions={toggle}>
      {current && <div className="climate-freshness">
        <strong>{t('climate.latestData')} · {date(current.end_date)}</strong>
        <span>{t('climate.availableNote')}</span>
      </div>}
      {current && <div className="stats">
        <Stat label={`${t('climate.rain')} · ${currentLabel}`} value={current.rain_mm ?? '—'} unit=" mm"
          note={`${t('climate.through')} ${date(current.dates.rain_mm)}`} />
        <Stat label={`${t('climate.heatDaysYear')} · ${currentLabel}`} value={current.heat_days} unit={` ${t('climate.daysUnit')}`}
          note={`${t('climate.through')} ${date(current.end_date)}`} />
        <Stat label={t('climate.temperatureChange')} value={current.t_mean_change_c == null ? '—' : sign(current.t_mean_change_c)} unit="°C"
          note={`${currentLabel} ${t('climate.samePeriod')} ${base}`} />
        <Stat label={t('climate.latestMax')} value={current.latest.t_max ?? '—'} unit="°C"
          note={date(current.latest.date)} />
      </div>}
      <details className="climate-history">
      <summary>{t('climate.longTerm')} · {recent}</summary>
      <div className="stats">
        <Stat label={t('climate.warmer')} value={sign(d.trend.t_mean_change_c)} unit="°C"
          note={`${recent} ${t('climate.vs')} ${base}`} />
        <Stat label={t('climate.heatDaysYear')} value={d.recent.heat_days} unit={` ${t('climate.daysUnit')}`}
          note={`${t('climate.was')} ${d.baseline.heat_days} (${base})`} />
        <Stat label={t('climate.frostFreeSeason')} value={sign(d.trend.frost_free_days_change)} unit={` ${t('climate.daysUnit')}`}
          note={`${t('climate.frostWindow')} ${d.recent.last_spring_frost} → ${d.recent.first_autumn_frost}`} />
        <Stat label={t('climate.rainYear')} value={Math.round(d.recent.rain_mm)} unit=" mm"
          note={`${sign(d.trend.rain_change_pct)}% ${t('climate.vs')} ${base}`} />
      </div>
      </details>

      {mode === 'simple' && <p className="note">{t('mode.climateSimple')}</p>}
      {mode === 'advanced' && <div className="chart-grid">
        <ChartCard title={t('climate.waterTitle')} term="et0"
          help={showCurrent ? `${t('climate.partialHelp')} ${t('climate.rain')}: ${date(current.dates.rain_mm)} · ET₀: ${date(current.dates.et0)}` : t('climate.waterHelp').replace('{n}', Math.abs(deficitTotal))}
          source={source(showCurrent ? `${current.start_date}–${current.end_date}` : recent)}>
          {current && <div className="segmented climate-period" role="group" aria-label={t('climate.period')}>
            <button aria-pressed={!historical} onClick={() => setHistorical(false)}>{currentLabel}</button>
            <button aria-pressed={historical} onClick={() => setHistorical(true)}>{recent} · {t('climate.average')}</button>
          </div>}
          <WaterBalanceChart monthly={showCurrent ? current.monthly : d.monthly.recent} />
        </ChartCard>

        <ChartCard title={t('climate.heatTitle')} term="heatDays" help={`${t('climate.heatHelp')} ${current?.partial ? t('climate.partialYearNote').replace('{year}', current.year) : ''}`} source={source(yearly[0].year + '–' + yearly.at(-1).year)}>
          <HeatDaysChart yearly={yearly} baselineAvg={d.baseline.heat_days} />
        </ChartCard>

        <ChartCard title={t('climate.frostTitle')} term="frostFree" help={`${t('climate.frostHelp')} ${t('climate.frostObserved')}`} source={source(yearly[0].year + '–' + yearly.filter((row) => row.last_spring_frost_doy && row.first_autumn_frost_doy).at(-1)?.year)}>
          <FrostChart yearly={yearly} />
        </ChartCard>

      </div>}
    </Screen>
  )
}
