import { MONTHS } from '../api.js'
import { Bars, Lines } from './charts.jsx'

export function Evidence({ profile }) {
  if (!profile) return null
  const c = profile.climate
  const nd = profile.ndvi
  const soil = profile.soil
  const ter = profile.terrain
  return (
    <section className="evidence-section">
      <div className="section-head">
        <p className="eyebrow">The evidence · what the data says about this place</p>
        <h2>{c.n_years} years of NASA data at this field</h2>
      </div>
      <div className="grid-2">
        <article className="card">
          <h3>Rain vs crop water demand</h3>
          <p className="muted small">Average per month, {c.years}. Crop demand is reference evapotranspiration (FAO-56
            Penman-Monteith). In {c.dry_months.map((m) => MONTHS[m - 1]).join(', ')} demand exceeds rain by more than 60 mm.</p>
          <Bars label="Monthly rain and crop water demand" unit=" mm"
            data={c.monthly.map((m) => ({ label: MONTHS[m.month - 1][0], tip: MONTHS[m.month - 1], rain: m.rain, et0: m.et0 }))}
            series={[{ name: 'Rain', key: 'rain', color: 'var(--series-1)' }, { name: 'Crop demand (ET0)', key: 'et0', color: 'var(--series-2)' }]} />
          <p className="source">{c.source.dataset}</p>
        </article>
        <article className="card">
          <h3>Hot days are increasing</h3>
          <p className="muted small">Days over 35 °C each year: {c.heat.days_per_year} on average, {c.heat.last_5_years} in the
            last 5 years{c.heat.trend_per_decade != null && ` (trend ${c.heat.trend_per_decade > 0 ? '+' : ''}${c.heat.trend_per_decade} per decade)`}.</p>
          <Bars label="Days over 35 °C per year" unit=" days"
            data={c.by_year.map((b) => ({ label: `'${String(b.year).slice(2)}`, tip: b.year, v: b.heat_days }))}
            series={[{ name: 'Days over 35 °C', key: 'v', color: 'var(--series-2)' }]} />
          <p className="source">{c.source.dataset}</p>
        </article>
        <article className="card">
          <h3>Frost and the growing season</h3>
          <dl className="facts">
            <div><dt>Last spring frost</dt><dd>{c.frost.last_spring_median}<small>1 year in 10 after {c.frost.last_spring_late_1_in_10}</small></dd></div>
            <div><dt>First autumn frost</dt><dd>{c.frost.first_autumn_median}<small>1 year in 10 before {c.frost.first_autumn_early_1_in_10}</small></dd></div>
            <div><dt>Frost-free days</dt><dd>{c.frost.frost_free_days_median}</dd></div>
            <div><dt>Heavy-rain days (≥ 20 mm)</dt><dd>{c.heavy_rain.days_per_year} / yr</dd></div>
          </dl>
          <h4>Driest summers</h4>
          <ul className="plain">{c.driest_summers.map((d) => <li key={d.year}><b>{d.year}</b>: crop demand exceeded rain by {d.summer_deficit} mm (Apr–Sep), {d.heat_days} hot days</li>)}</ul>
          <p className="source">{c.source.dataset}</p>
        </article>
        <article className="card">
          <h3>Land and soil</h3>
          <dl className="facts">
            {ter && <div><dt>Elevation</dt><dd>{ter.elevation_m} m</dd></div>}
            {ter && <div><dt>Slope</dt><dd>{ter.slope_deg}° <small>{ter.class}, erosion ×{ter.erosion_factor}</small></dd></div>}
            <div><dt>Soil</dt><dd>{soil.name}<small>{soil.sand_pct ?? '–'}% sand · {soil.clay_pct ?? '–'}% clay</small></dd></div>
            <div><dt>Organic matter</dt><dd>{soil.organic_matter_pct ?? '–'}%</dd></div>
            <div><dt>pH</dt><dd>{soil.ph ?? '–'}</dd></div>
            <div><dt>Holds water</dt><dd>{Math.round((soil.fc - soil.wp) * 1000)} mm/m<small>runoff group {soil.hsg}</small></dd></div>
          </dl>
          <p className="source">{ter?.source?.dataset}; {soil.source}</p>
        </article>
      </div>
      <article className="card">
        <h3>Greenness from space: when the field is bare</h3>
        {nd ? (
          <>
            <p className="muted small">NDVI over the field, every 16 days since 2016. Below {nd.thresholds.bare} the soil is bare.
              Recent years: about {nd.bare_days_avg_recent} bare days a year.
              {nd.stressed_years.length > 0 && ` Stressed summers: ${nd.stressed_years.map((s) => `${s.year} (−${s.drop_pct}%, rain Apr–Aug ${s.rain_apr_aug_pct_of_normal ?? '–'}% of normal)`).join(', ')}.`}</p>
            <Lines label="NDVI over time" height={200} yMax={1}
              xFormat={(v) => new Date(v).getFullYear()}
              refs={[{ y: nd.thresholds.bare, label: 'bare soil' }]}
              lines={[{ name: 'NDVI', color: 'var(--series-3)', points: nd.series.map((p) => ({ x: Date.parse(p.date), y: p.ndvi })) }]} />
            <ul className="plain small">
              {nd.years.slice(-4).map((y) => <li key={y.year}><b>{y.year}</b>: {y.pattern}; {y.bare_days} bare days</li>)}
            </ul>
            <p className="source">{nd.source.dataset} · {nd.pixels} pixel(s)</p>
          </>
        ) : <p className="muted">{profile.ndvi_status === 'loading' ? 'Downloading 10 years of MODIS greenness for this field (a few minutes)…' : 'No satellite greenness yet.'}</p>}
      </article>
    </section>
  )
}

export function FarmPlan({ plan }) {
  if (!plan) return null
  return (
    <section className="plan-section">
      <div className="section-head">
        <p className="eyebrow">Farm plan · all fields together</p>
        <h2>{plan.fields.length} fields, {plan.area_ha} ha</h2>
        <p className="muted">Uses each field's chosen rotation (or what it grows now). Gross income about €{plan.gross_eur_year.toLocaleString('en-US')} a year;
          irrigation about {plan.water_m3_year.toLocaleString('en-US')} m³ a year, most in {MONTHS[plan.peak_month - 1]}.</p>
      </div>
      {plan.warnings.length > 0 && (
        <ul className="alerts">{plan.warnings.map((w, i) => <li key={i} className="alert alert-watch"><b>{w.kind === 'pests' ? 'Pests' : w.kind === 'income' ? 'Income' : 'Neighbours'}</b> {w.text}</li>)}</ul>
      )}
      <div className="grid-2">
        <article className="card">
          <h3>Irrigation water by month</h3>
          <Bars label="Farm irrigation by month" unit=" m³"
            data={Object.entries(plan.water_m3_by_month).map(([m, v]) => ({ label: MONTHS[m - 1][0], tip: MONTHS[m - 1], v }))}
            series={[{ name: 'Irrigation', key: 'v', color: 'var(--series-1)' }]} />
        </article>
        <article className="card">
          <h3>The next three seasons</h3>
          <div className="table-wrap">
            <table className="compare">
              <thead><tr><th scope="col">Field</th>{plan.fields[0]?.seasons.map((s) => <th key={s.season}>{s.season}</th>)}</tr></thead>
              <tbody>
                {plan.fields.map((f) => (
                  <tr key={f.field_id}>
                    <th scope="row">{f.name}<small> {f.area_ha} ha</small></th>
                    {f.seasons.map((s) => <td key={s.season}>{s.crops.map((c) => <span key={c.id} className={`crop fam-${c.family}`}>{c.name}</span>)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </div>
    </section>
  )
}
