import { useEffect, useState } from 'react'
import { getClimate } from '../api.js'
import { FrostChart, HeatDaysChart, WaterBalanceChart } from '../components/ClimateCharts.jsx'
import Screen, { ComingSoon } from '../components/Screen.jsx'
import TermHelp from '../components/TermHelp.jsx'
import { load, useI18n } from '../i18n/index.jsx'

const sign = (v) => (v > 0 ? `+${v}` : `${v}`)

function Stat({ label, value, unit, note }) {
  return (
    <div className="card stat">
      <span className="label">{label}</span>
      <span className="stat-value">{value}<span className="tile-unit">{unit}</span></span>
      <span className="stat-note">{note}</span>
    </div>
  )
}

function ChartCard({ title, term, help, source, children }) {
  return (
    <div className="card chart-card">
      <h2>{title}{term && <TermHelp term={term} />}</h2>
      {help && <p className="chart-help">{help}</p>}
      {children}
      <p className="source">{source}</p>
    </div>
  )
}

export default function Climate() {
  const { t } = useI18n()
  const fieldId = load('niva.fieldId', '1')
  const [d, setD] = useState(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    getClimate(fieldId).then(setD).catch(() => setError(true))
  }, [fieldId])

  if (error) return <Screen section="climate"><p className="card">{t('server.down')}</p></Screen>
  if (!d) return <Screen section="climate"><p className="card muted">{t('field.loading')}</p></Screen>

  const src = d.sources[0]
  const base = d.periods.baseline
  const recent = d.periods.recent
  const source = (period) => `${src.dataset} · ${period} · ${d.location.name} (${d.location.lat}, ${d.location.lon})`
  const deficit = d.monthly.recent.filter((m) => m.balance_mm < 0)
  const deficitTotal = Math.round(deficit.reduce((s, m) => s + m.balance_mm, 0))

  return (
    <Screen section="climate">
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

      <div className="chart-grid">
        <ChartCard title={t('climate.waterTitle')} term="et0"
          help={t('climate.waterHelp').replace('{n}', Math.abs(deficitTotal))}
          source={source(recent)}>
          <WaterBalanceChart monthly={d.monthly.recent} />
        </ChartCard>

        <ChartCard title={t('climate.heatTitle')} term="heatDays" help={t('climate.heatHelp')} source={source(d.yearly[0].year + '–' + d.yearly.at(-1).year)}>
          <HeatDaysChart yearly={d.yearly} baselineAvg={d.baseline.heat_days} />
        </ChartCard>

        <ChartCard title={t('climate.frostTitle')} term="frostFree" help={t('climate.frostHelp')} source={source(d.yearly[0].year + '–' + d.yearly.at(-1).year)}>
          <FrostChart yearly={d.yearly} />
        </ChartCard>

        <ChartCard title={t('climate.greenTitle')} source="MODIS NDVI MOD13Q1, 250 m">
          <ComingSoon>{t('climate.greenPending')}</ComingSoon>
        </ChartCard>
      </div>
    </Screen>
  )
}
