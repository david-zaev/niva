import { useState } from 'react'

const eur = (n) => `€${Number(n).toLocaleString('en-US')}`

// How an option compares with what the farmer grows now, in words: "43% less than now"
function change(value, now, moreIsBetter, unit = '%') {
  if (now == null || value === now) return { text: 'same as now', tone: 'same' }
  const better = moreIsBetter ? value > now : value < now
  let text
  if (unit === '%') text = `now ${now}%`
  else if (!now) text = value > now ? 'now none' : 'same as now'
  else text = `${Math.abs(Math.round((100 * (value - now)) / now))}% ${value > now ? 'more' : 'less'} than now`
  return { text, tone: better ? 'better' : 'worse' }
}

function Row({ label, value, cmp, hint }) {
  return (
    <div className="plain-row">
      <dt>{label}<small>{hint}</small></dt>
      <dd>
        <b>{value}</b>
        {cmp && <span className={`delta delta-${cmp.tone}`}>{cmp.text}</span>}
      </dd>
    </div>
  )
}

function Card({ r, now, chosen, onChoose }) {
  const [open, setOpen] = useState(false)
  const c = r.card
  const isCurrent = r.kind === 'current'
  const m = r.metrics
  const n = isCurrent ? null : now.metrics
  const inShort = isCurrent ? r.idea : (c.why[0] ?? r.idea)
  return (
    <article className={`rot-card ${isCurrent ? 'is-current' : ''} ${chosen ? 'is-chosen' : ''}`}>
      <header>
        <p className="eyebrow">{isCurrent ? 'What you grow now' : r.option === 1 ? 'Option 1 · best match' : `Option ${r.option}`}</p>
        <h3>{r.name.replace(' (now)', '')}</h3>
        <ol className="seasons">
          {r.season_names.map((s, i) => <li key={i}><small>Year {i + 1}</small>{s}</li>)}
        </ol>
      </header>
      {inShort && <p className="in-short">{inShort}</p>}
      <dl className="plain-rows">
        <Row label="Water" hint="irrigation a year" value={m.irrigation_mm ? `${m.irrigation_mm} mm` : 'none'}
          cmp={n && change(m.irrigation_mm, n.irrigation_mm, false, 'mm')} />
        <Row label="Soil covered" hint="by living plants" value={`${m.living_cover_pct}% of the year`}
          cmp={n && change(m.living_cover_pct, n.living_cover_pct, true)} />
        <Row label="Dry year" hint="harvest kept in the driest years" value={`${m.dry_year_yield_pct}%`}
          cmp={n && change(m.dry_year_yield_pct, n.dry_year_yield_pct, true)} />
        <Row label="Income" hint="gross, per hectare" value={eur(m.gross_eur_ha)}
          cmp={n && change(m.gross_eur_ha, n.gross_eur_ha, true, 'eur')} />
      </dl>
      <button className="read-more" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? 'Show less' : 'Read more: why, risks, evidence'}</button>
      {open && (
        <div className="rot-details">
          {c.why.length > 0 && <><h4>Why</h4><ul>{c.why.map((t, i) => <li key={i}>{t}</li>)}</ul></>}
          {c.risks.length > 0 && <><h4>Check before you switch</h4><ul>{c.risks.map((t, i) => <li key={i}>{t}</li>)}</ul></>}
          <h4>Evidence</h4>
          <ul className="evidence">{c.evidence.map((e, i) => <li key={i}>{e.text}<small>{e.source}</small></li>)}</ul>
          <h4>What we do not know yet</h4><ul className="muted">{c.gaps.map((t, i) => <li key={i}>{t}</li>)}</ul>
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
  if (!data) return <section className="card"><p className="muted">Testing crop rotations against 25 years of NASA data for this field…</p></section>
  const [now, ...options] = data.rotations
  const cards = [now, ...options.map((r, i) => ({ ...r, option: i + 1 }))]
  return (
    <section className="rotations">
      <div className="section-head">
        <p className="eyebrow">Crop rotation plans · from NASA data for this field</p>
        <h2>{options.length ? `${options.length} rotations to consider for this field` : 'No other rotation fits this field'}</h2>
        <p className="muted">
          We played every rotation through each season of {data.climate_years} at this field, day by day, with the
          real NASA weather, the field&apos;s slope and its soil. Only rotations for a {data.farm_type} farm
          that still give a harvest in dry years with {data.irrigation === 'none' ? 'no irrigation' : `${data.irrigation} irrigation`} are shown.
        </p>
      </div>
      <div className="rot-grid">
        {cards.map((r) => <Card key={r.id} r={r} now={now} chosen={data.chosen === r.id} onChoose={onChoose} />)}
      </div>
      {(data.others?.length > 0 || data.not_offered?.length > 0) && (
        <div className="rot-also muted small">
          {data.others?.length > 0 && <p>Also tested, ranked lower: {data.others.map((o) => o.name).join(', ')}.</p>}
          {data.not_offered?.length > 0 && (
            <p>Not offered for this field: {data.not_offered.map((o) => `${o.name} (${o.because})`).join('; ')}.</p>
          )}
        </div>
      )}
    </section>
  )
}
