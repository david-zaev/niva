import { getMetrics, getNdvi, getSoil, getWeather, paths } from '../api.js'
import { useI18n } from '../i18n/index.jsx'
import { NdviChart, WaterUseChart, WetnessChart } from './FieldCharts.jsx'
import TermHelp from './TermHelp.jsx'
import { fmt, useCrops, useData, useDay } from './util.js'

function Waiting({ error }) {
  const { t } = useI18n()
  return <p className="muted small">{error?.status === 503 ? t('metrics.waiting') : error ? t('server.down') : t('field.loading')}</p>
}

const src = (list) => <p className="source">{list.map((x) => `${x.dataset} (${x.dates})`).join(' · ')}</p>

// Advanced view of My field: the numbers behind the summary banner
export default function FieldMetrics({ fieldId }) {
  const { t } = useI18n()
  const day = useDay()
  const { cropName } = useCrops()
  const m = useData(() => getMetrics(fieldId), paths.metrics(fieldId), [fieldId])
  const soil = useData(() => getSoil(fieldId), paths.soil(fieldId), [fieldId])
  const ndvi = useData(() => getNdvi(fieldId), paths.ndvi(fieldId), [fieldId])
  const wx = useData(() => getWeather(fieldId), paths.weather(fieldId), [fieldId])
  const bal = m.data?.water_balance

  return (
    <div className="chart-grid">
      <article className="card chart-card">
        <div className="card-head"><h2>{t('metrics.wetTitle')}<TermHelp term="gwet" /></h2></div>
        <p className="chart-help">{t('metrics.wetHelp')}</p>
        {m.data ? <><WetnessChart daily={m.data.daily} />{src(m.data.sources)}</> : <Waiting error={m.error} />}
      </article>

      <article className="card chart-card">
        <div className="card-head"><h2>{t('metrics.waterTitle')}<TermHelp term="eta" /></h2></div>
        {bal && <p className="chart-help">
          {fmt(t('metrics.waterLine'), { days: bal.days, rain: bal.rain_mm, et0: bal.et0_mm })}{' '}
          {bal.eta_mm != null
            ? fmt(t('metrics.etaLine'), { crop: cropName(bal.crop), kc: bal.kc, eta: bal.eta_mm, bal: bal.balance_mm > 0 ? `+${bal.balance_mm}` : bal.balance_mm })
            : t('metrics.noKc')}
        </p>}
        {m.data ? <><WaterUseChart daily={m.data.daily} />{bal?.kc_source && <p className="source">Kc: {bal.kc_source}</p>}</> : <Waiting error={m.error} />}
      </article>

      <article className="card chart-card">
        <div className="card-head"><h2>{t('metrics.ndviTitle')}<TermHelp term="ndvi" /></h2>
          {ndvi.data && <span className="status">{t(`metrics.ndvi_${ndvi.data.level}`)}</span>}</div>
        {ndvi.data
          ? <>
              <p className="chart-help">
                {fmt(t('metrics.ndviLine'), { v: ndvi.data.latest.ndvi.toFixed(2), date: day(ndvi.data.latest.day, { day: 'numeric', month: 'short', year: 'numeric' }) })}{' '}
                {ndvi.data.change != null && fmt(t(ndvi.data.change >= 0 ? 'metrics.ndviUp' : 'metrics.ndviDown'), { v: Math.abs(ndvi.data.change).toFixed(2) })}
              </p>
              <NdviChart points={ndvi.data.points} />
              {src([ndvi.data.source])}
            </>
          : <Waiting error={ndvi.error} />}
      </article>

      <article className="card chart-card">
        <div className="card-head"><h2>{t('metrics.soilTitle')}<TermHelp term="soilProfile" /></h2>
          {soil.data && <span className="status">{t(`texture.${soil.data.topsoil.texture}`)}</span>}</div>
        {soil.data
          ? <>
              <p className="chart-help">{fmt(t('metrics.soilLine'), { tex: t(`texture.${soil.data.topsoil.texture}`), ph: soil.data.topsoil.ph, taw: soil.data.topsoil.taw_mm_per_m })}</p>
              <div className="table-wrap">
                <table className="data-table">
                  <thead><tr><th>{t('metrics.depth')}</th><th>{t('metrics.clay')} %</th><th>{t('metrics.sand')} %</th><th>{t('metrics.silt')} %</th><th>pH</th><th>SOC g/kg</th><th>CEC</th><th>{t('metrics.bulk')}</th></tr></thead>
                  <tbody>{soil.data.layers.map((l) => (
                    <tr key={l.depth}><td>{l.depth}</td><td>{l.clay ?? '—'}</td><td>{l.sand ?? '—'}</td><td>{l.silt ?? '—'}</td><td>{l.phh2o ?? '—'}</td><td>{l.soc ?? '—'}</td><td>{l.cec ?? '—'}</td><td>{l.bdod ?? '—'}</td></tr>
                  ))}</tbody>
                </table>
              </div>
              <p className="source">{soil.data.source.dataset} ({soil.data.source.dates}) · TAW: {soil.data.taw_source}</p>
            </>
          : <Waiting error={soil.error} />}
      </article>

      <article className="card chart-card">
        <div className="card-head"><h2>{t('metrics.weekTitle')}</h2></div>
        {wx.data
          ? <>
              <div className="table-wrap">
                <table className="data-table">
                  <thead><tr><th /><th>°C</th><th>{t('metrics.rain')} mm</th><th>%</th><th>km/h</th><th>ET₀</th></tr></thead>
                  <tbody>{wx.data.days.map((d) => (
                    <tr key={d.day}><td>{day(d.day)}</td><td>{Math.round(d.t_min)}…{Math.round(d.t_max)}</td><td>{d.rain_mm}</td><td>{d.rain_prob ?? '—'}</td><td>{Math.round(d.wind_kmh)}</td><td>{d.et0}</td></tr>
                  ))}</tbody>
                </table>
              </div>
              {src([wx.data.source])}
            </>
          : <Waiting error={wx.error} />}
      </article>
    </div>
  )
}
