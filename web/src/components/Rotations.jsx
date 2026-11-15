import { useState } from 'react'
import { useI18n } from '../i18n/index.jsx'
import Toggle from './Toggle.jsx'

const eur = (n) => `€${Number(n).toLocaleString('en-US')}`

// How an option compares with what the farmer grows now, in words: "43% less than now"
function change(t, value, now, moreIsBetter, unit = '%') {
  if (now == null || value === now) return { text: t('app.rot.same'), tone: 'same' }
  const better = moreIsBetter ? value > now : value < now
  let text
  if (unit === '%') text = t('app.rot.nowPct', { n: now })
  else if (!now) text = value > now ? t('app.rot.nowNone') : t('app.rot.same')
  else {
    const n = Math.abs(Math.round((100 * (value - now)) / now))
    text = t(value > now ? 'app.rot.more' : 'app.rot.less', { n })
  }
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

function Card({ r, now }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const c = r.card
  const isCurrent = r.kind === 'current'
  const m = r.metrics
  const n = isCurrent || !now ? null : now.metrics
  const inShort = isCurrent ? r.idea : (c.why[0] ?? r.idea)
  const label = isCurrent ? t('app.rot.now') : r.option === 1 && !r.low_income ? t('app.rot.best') : t('app.rot.option', { n: r.option })
  return (
    <article className={`rot-card ${isCurrent ? 'is-current' : ''}`}>
      <header>
        <p className="eyebrow">{label}</p>
        <h3>{r.name.replace(/ \((now|сега)\)$/, '')}</h3>
        <ol className="seasons">
          {r.season_names.map((s, i) => <li key={i}><small>{t('app.rot.year', { n: i + 1 })}</small>{s}</li>)}
        </ol>
      </header>
      {inShort && <p className="in-short">{inShort}</p>}
      {c.income_warning && <p className="income-warn" role="note">{c.income_warning}</p>}
      <dl className="plain-rows">
        <Row label={t('app.rot.water')} hint={t('app.rot.waterHint')} value={m.irrigation_mm ? `${m.irrigation_mm} mm` : t('app.rot.noneWater')}
          cmp={n && change(t, m.irrigation_mm, n.irrigation_mm, false, 'mm')} />
        <Row label={t('app.rot.cover')} hint={t('app.rot.coverHint')} value={t('app.rot.coverVal', { n: m.living_cover_pct })}
          cmp={n && change(t, m.living_cover_pct, n.living_cover_pct, true)} />
        <Row label={t('app.rot.dry')} hint={t('app.rot.dryHint')} value={`${m.dry_year_yield_pct}%`}
          cmp={n && change(t, m.dry_year_yield_pct, n.dry_year_yield_pct, true)} />
        <Row label={t('app.rot.income')} hint={t('app.rot.incomeHint')} value={eur(m.gross_eur_ha)}
          cmp={n && change(t, m.gross_eur_ha, n.gross_eur_ha, true, 'eur')} />
      </dl>
      <div className="rot-footer">
        <Toggle open={open} onClick={() => setOpen(!open)} more={t('app.rot.details')} less={t('app.rot.hide')} />
        {open && (
        <div className="rot-details">
          {c.why.length > 0 && <><h4>{t('app.rot.why')}</h4><ul>{c.why.map((x, i) => <li key={i}>{x}</li>)}</ul></>}
          {c.risks.length > 0 && <><h4>{t('app.rot.risks')}</h4><ul>{c.risks.map((x, i) => <li key={i}>{x}</li>)}</ul></>}
          <h4>{t('app.rot.evidence')}</h4>
          <ul className="evidence">{c.evidence.map((e, i) => <li key={i}>{e.text}<small>{e.source}</small></li>)}</ul>
          <h4>{t('app.rot.gaps')}</h4><ul className="muted">{c.gaps.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </div>
        )}
      </div>
    </article>
  )
}

// The one answer most farmers want: what goes in the ground next, and after that
function PlantNext({ r, compared }) {
  const { t } = useI18n()
  // the second crop in a season sits mid-sentence ("…; then pepper"), so it starts in lower case
  const step = (s, i) => {
    const crop = i > 0 ? s.name.charAt(0).toLowerCase() + s.name.slice(1) : s.name
    if (s.kept) return t('app.rot.stays', { crop })
    if (s.cover && s.end_part) return t('app.rot.coverStepEnd', { crop, month: s.sow_month, end: t(`app.rot.part_${s.end_part}`, { month: s.end_month }) })
    if (s.cover) return t('app.rot.coverStep', { crop, month: s.sow_month })
    return t(s.transplanted ? 'app.rot.planted' : 'app.rot.sown', { crop, month: s.sow_month })
  }
  const [next, ...then] = r.plant_next
  return (
    <section className="card plant-next">
      <p className="eyebrow">{t('app.rot.nextEyebrow')}</p>
      <h2>{next.steps.filter((s) => !s.cover).map((s) => s.name).join(' + ') || next.steps[0].name}</h2>
      <ol className="plan-steps">
        <li><b>{t('app.rot.nextSeason')}</b><span>{next.steps.map(step).join(t('app.rot.join'))}</span></li>
        {then.map((x, i) => (
          <li key={i}><b>{i === 0 ? t('app.rot.after') : t('app.rot.then')}</b><span>{x.steps.map(step).join(t('app.rot.join'))}</span></li>
        ))}
      </ol>
      <p className="muted small">{t(compared ? 'app.rot.from' : 'app.rot.fromOpen', { name: r.name })} {r.card.why[0]}</p>
    </section>
  )
}

export default function Rotations({ data }) {
  const { t } = useI18n()
  const [tab, setTab] = useState(null)
  if (!data) {
    return (
      <section className="card loading-card" aria-busy="true">
        <div className="loading-head"><span className="spinner" aria-hidden="true" /><p>{t('app.rot.loading')}</p></div>
        <div className="loading-bar" aria-hidden="true"><span /></div>
        <div className="skeleton" aria-hidden="true"><i /><i /><i /><i /></div>
      </section>
    )
  }
  // with no current crops entered there is nothing to compare with: options only
  const hasNow = data.rotations[0]?.kind === 'current'
  const [now, ...options] = hasNow ? data.rotations : [null, ...data.rotations]
  const cards = [...(hasNow ? [now] : []), ...options.map((r, i) => ({ ...r, option: i + 1 }))]
  const best = options[0]
  const shown = cards.find((r) => r.id === tab) ?? cards[hasNow && best ? 1 : 0]
  const tabName = (r) => r.kind === 'current' ? t('app.rot.tabNow') : r.option === 1 && !r.low_income ? t('app.rot.tabBest') : t('app.rot.option', { n: r.option })
  const kind = { vegetable: 'farm_vegetable', tobacco: 'farm_tobacco', 'field crop': 'farm_field crop' }[data.farm_type]
  const water = data.irrigation === 'none' || !data.irrigation
    ? t('app.rot.noIrr')
    : t('app.rot.withIrr', { kind: t(`app.map.${data.irrigation}`).toLowerCase() })
  return (
    <>
      {best && <PlantNext r={best} compared={hasNow} />}
      <section className="rotations">
        <div className="section-head">
          <p className="eyebrow">{t('app.rot.eyebrow')}</p>
          <h2>{!options.length ? t('app.rot.noneFit') : t(hasNow ? 'app.rot.title' : 'app.rot.titleOpen', { n: options.length })}</h2>
          <p className="muted">
            {hasNow
              ? t('app.rot.intro', { years: data.climate_years, farm: kind ? t(`app.rot.${kind}`) : data.farm_type, water })
              : t('app.rot.introOpen', { years: data.climate_years, water })}
          </p>
        </div>
        <div className="rot-tabs" role="tablist" aria-label={t('app.rot.tabsLabel')}>
          {cards.map((r) => (
            <button key={r.id} type="button" role="tab" aria-selected={r.id === shown.id}
              className={`rot-tab ${r.id === shown.id ? 'is-on' : ''}`} onClick={() => setTab(r.id)}>
              <b>{tabName(r)}</b>
              <small>{r.name.replace(/ \((now|сега)\)$/, '')}</small>
            </button>
          ))}
        </div>
        <div role="tabpanel">
          <Card key={shown.id} r={shown} now={now} />
        </div>
      </section>
    </>
  )
}
