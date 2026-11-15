import { useState } from 'react'

const SCORE_NAMES = { water: 'Water', soil: 'Soil health', resilience: 'Resilience', income: 'Income' }

function fmt(n) {
  return n == null ? '–' : Number(n).toLocaleString('en-US')
}

function ScoreBars({ scores }) {
  return (
    <div className="scorebars">
      {Object.entries(SCORE_NAMES).map(([k, name]) => (
        <div key={k} className="scorebar">
          <span>{name}</span>
          <div className="bar"><i style={{ width: `${scores[k]}%` }} /></div>
          <b>{scores[k]}</b>
        </div>
      ))}
    </div>
  )
}

function Card({ r, chosen, onChoose }) {
  const [open, setOpen] = useState(r.kind !== 'current')
  const c = r.card
  const isCurrent = r.kind === 'current'
  return (
    <article className={`rot-card ${isCurrent ? 'is-current' : ''} ${chosen ? 'is-chosen' : ''}`}>
      <header>
        <p className="eyebrow">{isCurrent ? 'What you grow now' : `Option · rank ${r.rank}`}</p>
        <h3>{r.name}</h3>
        <ol className="seasons">
          {r.season_names.map((s, i) => <li key={i}><small>Season {i + 1}</small>{s}</li>)}
        </ol>
        <div className="overall"><b>{r.score}</b><span>overall score</span></div>
      </header>
      <ScoreBars scores={r.scores} />
      <dl className="facts">
        <div><dt>Irrigation</dt><dd>{r.metrics.irrigation_mm} mm/yr<small>dry year {r.metrics.irrigation_mm_dry_year}</small></dd></div>
        <div><dt>Soil covered</dt><dd>{r.metrics.living_cover_pct}%<small>{r.metrics.bare_days} bare days</small></dd></div>
        <div><dt>Nitrogen added</dt><dd>{r.metrics.n_credit_kg_ha} kg/ha</dd></div>
        <div><dt>Dry-year yield</dt><dd>{r.metrics.dry_year_yield_pct}%</dd></div>
        <div><dt>Gross income</dt><dd>€{fmt(r.metrics.gross_eur_ha)}/ha</dd></div>
      </dl>
      <button className="read-more" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? 'Hide details' : 'Why, evidence, risks'}</button>
      {open && (
        <div className="rot-details">
          <h4>Why</h4><ul>{c.why.map((t, i) => <li key={i}>{t}</li>)}</ul>
          <h4>Benefits</h4><ul>{c.benefits.map((t, i) => <li key={i}>{t}</li>)}</ul>
          <h4>Evidence</h4>
          <ul className="evidence">{c.evidence.map((e, i) => <li key={i}>{e.text}<small>{e.source}</small></li>)}</ul>
          <h4>Risks for local review</h4><ul>{c.risks.map((t, i) => <li key={i}>{t}</li>)}</ul>
          <h4>Information gaps</h4><ul className="muted">{c.gaps.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </div>
      )}
      {!isCurrent && (
        <button className={`btn ${chosen ? 'btn-ghost' : 'btn-volt'}`} onClick={() => onChoose(chosen ? null : r.id)}>
          {chosen ? 'Chosen for the farm plan ✓' : 'Choose this rotation'}
        </button>
      )}
    </article>
  )
}

export default function Rotations({ data, onChoose }) {
  if (!data) return <section className="card"><p className="muted">Replaying 25 years of NASA data for this field…</p></section>
  const cur = data.rotations[0]
  return (
    <section className="rotations">
      <div className="section-head">
        <p className="eyebrow">Crop rotation plans · from location data only</p>
        <h2>{data.rotations.length - 1} rotations compared with what you grow now</h2>
        <p className="muted">
          Each rotation was replayed day by day through every season {data.climate_years} at this field: NASA POWER
          weather, NASADEM slope ({data.terrain ? `${data.terrain.slope_deg}°` : 'n/a'}), and the soil map
          ({data.soil.name.toLowerCase()}, {data.soil.clay_pct ?? '–'}% clay). Irrigation: {data.irrigation}.
          {data.smap_check && ` The simulated soil water tracks NASA SMAP soil moisture here (r = ${data.smap_check.r}).`}
        </p>
      </div>

      <div className="table-wrap">
        <table className="compare">
          <thead>
            <tr><th scope="col">Rotation</th><th>Score</th><th>Irrigation mm/yr</th><th>Soil covered</th><th>Erosion index</th><th>N kg/ha</th><th>Dry-year yield</th><th>Gross €/ha</th></tr>
          </thead>
          <tbody>
            {data.rotations.map((r) => (
              <tr key={r.id} className={r.kind === 'current' ? 'is-current' : ''}>
                <th scope="row">{r.name}{r.kind === 'current' && <small> (now)</small>}</th>
                <td>{r.score}</td>
                <td className={r.metrics.irrigation_mm < cur.metrics.irrigation_mm ? 'better' : ''}>{r.metrics.irrigation_mm}</td>
                <td className={r.metrics.living_cover_pct > cur.metrics.living_cover_pct ? 'better' : ''}>{r.metrics.living_cover_pct}%</td>
                <td className={r.metrics.erosion_index < cur.metrics.erosion_index ? 'better' : ''}>{r.metrics.erosion_index}</td>
                <td className={r.metrics.n_credit_kg_ha > cur.metrics.n_credit_kg_ha ? 'better' : ''}>{r.metrics.n_credit_kg_ha}</td>
                <td className={r.metrics.dry_year_yield_pct > cur.metrics.dry_year_yield_pct ? 'better' : ''}>{r.metrics.dry_year_yield_pct}%</td>
                <td className={r.metrics.gross_eur_ha > cur.metrics.gross_eur_ha ? 'better' : ''}>{fmt(r.metrics.gross_eur_ha)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rot-grid">
        {data.rotations.map((r) => <Card key={r.id} r={r} chosen={data.chosen === r.id} onChoose={onChoose} />)}
      </div>
      {data.others?.length > 0 && (
        <p className="muted small">Also simulated: {data.others.map((o) => `${o.name} (${o.score})`).join(', ')}.</p>
      )}
    </section>
  )
}
