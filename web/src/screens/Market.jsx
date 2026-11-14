import { useState } from 'react'
import { fieldId as currentField, getMarket, paths } from '../api.js'
import { ProductionChart } from '../components/FieldCharts.jsx'
import { ModeToggle, useMode } from '../components/Mode.jsx'
import Screen from '../components/Screen.jsx'
import TermHelp from '../components/TermHelp.jsx'
import { fmt, useData } from '../components/util.js'
import { useI18n } from '../i18n/index.jsx'

const ARROW = { up: '▲', down: '▼', steady: '■' }

function Trend({ tr }) {
  const { t } = useI18n()
  if (!tr) return <span className="muted small">{t('market.noData')}</span>
  return (
    <span className={`trend trend-${tr.direction}`}>
      {ARROW[tr.direction]} {t(`market.dir_${tr.direction}`)}
      <span className="muted small"> {tr.production_change_pct > 0 ? '+' : ''}{tr.production_change_pct}%</span>
    </span>
  )
}

// Where to sell: the places that reported a ZPIS price for one crop, best price first, with distance from the field
function SellPlaces({ crops, currency }) {
  const { t } = useI18n()
  const withPlaces = crops.filter((c) => c.places?.length)
  const [pick, setPick] = useState(null)
  const c = withPlaces.find((x) => x.crop === pick) ?? withPlaces[0]
  if (!c) return <p className="note">{t('market.noPlaces')}</p>
  const best = Math.max(...c.places.map((x) => x.price))
  const kms = c.places.map((x) => x.km).filter((k) => k != null)
  const nearest = kms.length ? Math.min(...kms) : null
  return (
    <>
      <div className="chip-row" role="group" aria-label={t('market.sellTitle')}>
        {withPlaces.map((x) => <button key={x.crop} className="chip chip-btn" aria-pressed={x.crop === c.crop} onClick={() => setPick(x.crop)}>{x.label}</button>)}
      </div>
      <p className="muted small">{c.prices[0].product} · {t(`market.m_${c.prices[0].market}`)}</p>
      <div className="table-wrap">
        <table className="data-table sell-table">
          <thead><tr><th>{t('market.place')}</th><th>{currency}</th><th>{t('market.distance')}</th><th /></tr></thead>
          <tbody>{c.places.map((x) => (
            <tr key={x.place} className={x.price === best ? 'is-current' : ''}>
              <td><strong>{x.place}</strong></td>
              <td><strong>{x.price.toFixed(2)}</strong>{x.price === best && <span className="pill pill-volt tag">{t('market.best')}</span>}</td>
              <td>{x.km != null ? `${x.km} km` : '—'}{x.km != null && x.km === nearest && <span className="pill tag">{t('market.nearest')}</span>}</td>
              <td>{x.lat != null && <a href={`https://www.openstreetmap.org/?mlat=${x.lat}&mlon=${x.lon}#map=12/${x.lat}/${x.lon}`} target="_blank" rel="noreferrer">{t('market.showMap')} ↗</a>}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </>
  )
}

function CropDetail({ c }) {
  const { t } = useI18n()
  return (
    <article className="card chart-card">
      <div className="card-head"><h2>{c.label}</h2><Trend tr={c.trend} /></div>
      {c.trend && <p className="chart-help">{fmt(t('market.trendLine'), { area: c.trend.area_ha.toLocaleString(), prod: c.trend.production_t.toLocaleString(), years: c.trend.last_years, a: `${c.trend.area_change_pct > 0 ? '+' : ''}${c.trend.area_change_pct}`, before: c.trend.before_years })}</p>}
      <ProductionChart series={c.series} />
      <div className="table-wrap">
        <table className="data-table">
          <thead><tr><th>{t('market.year')}</th><th>{t('market.area')}</th><th>{t('market.produced')} t</th><th>t/ha</th><th>{t('market.sold')} t <TermHelp term="soldMissing" /></th></tr></thead>
          <tbody>{c.series.slice().reverse().map((r) => (
            <tr key={r.year}><td>{r.year}</td><td>{r.area_ha?.toLocaleString() ?? '—'}</td><td>{r.production_t?.toLocaleString() ?? '—'}</td>
              <td>{r.area_ha && r.production_t ? (r.production_t / r.area_ha).toFixed(1) : '—'}</td><td className="muted">—</td></tr>
          ))}</tbody>
        </table>
      </div>
    </article>
  )
}

export default function Market() {
  const { t, lang } = useI18n()
  const fieldId = currentField()
  const [mode, setMode] = useMode('market')
  const [open, setOpen] = useState(null)
  const { data, error } = useData(() => getMarket(fieldId), paths.market(fieldId), [fieldId])
  const toggle = <ModeToggle mode={mode} setMode={setMode} />
  if (!data) return <Screen section="market" actions={toggle}><p className="card muted">{error ? t('server.down') : t('field.loading')}</p></Screen>

  const crops = data.crops.map((c) => ({ ...c, label: lang === 'mk' ? c.name_mk : c.name }))
  const priced = crops.filter((c) => c.prices.length)
  const region = lang === 'mk' ? data.region_name_mk : data.region_name
  const up = crops.filter((c) => c.trend?.direction === 'up').map((c) => c.label)
  const down = crops.filter((c) => c.trend?.direction === 'down').map((c) => c.label)

  return (
    <Screen section="market" eyebrow={region} actions={toggle}>
      <article className="card banner">
        <div className="card-head"><h2>{fmt(t('market.inRegion'), { region })}</h2></div>
        {up.length > 0 && <p><span className="trend trend-up">▲</span> {fmt(t('market.growingMore'), { crops: up.join(', ') })}</p>}
        {down.length > 0 && <p><span className="trend trend-down">▼</span> {fmt(t('market.growingLess'), { crops: down.join(', ') })}</p>}
        <p className="muted small">{t('market.soldMissing')}</p>
      </article>

      <article className="card">
        <div className="card-head"><h2>{t('market.pricesTitle')}</h2><span className="muted small">{data.currency} · {fmt(t('market.retrieved'), { d: data.price_retrieved })}</span></div>
        <ul className="market-list">
          {crops.map((c) => {
            const p = c.prices[0]
            return (
              <li key={c.crop}>
                <button className="market-row" onClick={() => setOpen(open === c.crop ? null : c.crop)} aria-expanded={open === c.crop}>
                  <span className="market-name">{c.label}</span>
                  <span className="market-price">
                    {c.local_price != null ? <><strong>{c.local_price}</strong> <span className="muted small">{t('market.local')}</span></>
                      : p ? <><strong>{p.price}</strong> <span className="muted small">{t(`market.m_${p.market}`)}</span></>
                        : <span className="muted small">{t('market.noPrice')}</span>}
                  </span>
                  <Trend tr={c.trend} />
                </button>
                {open === c.crop && <div className="market-more">
                  {c.prices.map((x, i) => <p key={i} className="small">{x.product}: <strong>{x.price}</strong> {data.currency} · {t(`market.m_${x.market}`)} · {x.scope} {x.url && <a href={x.url} target="_blank" rel="noreferrer">ZPIS ↗</a>}</p>)}
                  {mode === 'simple' && c.trend && <p className="small muted">{fmt(t('market.trendShort'), { prod: c.trend.production_t.toLocaleString(), years: c.trend.last_years })}</p>}
                </div>}
              </li>
            )
          })}
        </ul>
      </article>

      <article className="card">
        <div className="card-head"><h2>{t('market.sellTitle')}</h2></div>
        <p className="chart-help">{t('market.sellHelp')}</p>
        <SellPlaces crops={crops} currency={data.currency} />
        <p className="source">{data.sources[1].dataset} ({data.sources[1].dates}) · {data.sources[2]?.dataset}</p>
      </article>

      <article className="card">
        <div className="card-head"><h2>{t('market.kindsTitle')}</h2></div>
        <ul className="where-list">
          <li><strong>{t('market.m_buyout')}</strong> — {t('market.buyoutHelp')}</li>
          <li><strong>{t('market.m_wholesale')}</strong> — {t('market.wholesaleHelp')}</li>
          <li><strong>{t('market.processors')}</strong> — {t('market.processorsHelp')}</li>
          <li><strong>{t('market.green')}</strong> — {t('market.greenHelp')}</li>
        </ul>
        {data.buyers.length === 0 && <p className="note">{t('market.noBuyers')}</p>}
        <p className="small"><a href="https://zpis.gov.mk/" target="_blank" rel="noreferrer">{t('market.zpisLink')} ↗</a> · <a href="https://ponudapobaruvacka.zpis.gov.mk/" target="_blank" rel="noreferrer">ponudapobaruvacka.zpis.gov.mk ↗</a></p>
      </article>

      {mode === 'advanced' && <>
        <h2 className="section-title">{fmt(t('market.analyzer'), { region })}</h2>
        <p className="note">{fmt(t('market.municipalities'), { list: data.municipalities.join(', ') })}</p>
        <div className="chart-grid two">
          {crops.filter((c) => c.series.length).map((c) => <CropDetail key={c.crop} c={c} />)}
        </div>
      </>}

      <p className="source">{data.sources.map((x) => `${x.dataset} (${x.dates})`).join(' · ')}</p>
    </Screen>
  )
}
