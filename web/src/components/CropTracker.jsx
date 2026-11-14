import { useEffect, useRef, useState } from 'react'
import { addHarvest, addPlanting, deleteHarvest, deletePlanting, getHarvests, getPlantings, paths } from '../api.js'
import { useI18n } from '../i18n/index.jsx'
import { YieldChart } from './FieldCharts.jsx'
import { fmt, today, useCrops, useData, useDay } from './util.js'

const blankHarvest = (crop = '', plantingId = null) => ({
  crop, harvested_on: today(), amount_kg: '', sold_kg: '', area_ha: '', price_mkd_kg: '', quality: '', notes: '', planting_id: plantingId,
})

// What is planted (for harvest alerts), and what came off the field (the farmer's own yield history)
export default function CropTracker({ fieldId, owner, harvestFor, onChange }) {
  const { t } = useI18n()
  const day = useDay()
  const { list: crops, cropName } = useCrops()
  const plantings = useData(() => getPlantings(fieldId), paths.plantings(fieldId), [fieldId])
  const harvests = useData(() => getHarvests(fieldId), paths.harvests(fieldId), [fieldId])
  const [plant, setPlant] = useState({ crop: '', planted_on: today() })
  const [hv, setHv] = useState(null)
  const [msg, setMsg] = useState(null)
  const form = useRef(null)

  useEffect(() => {
    if (!harvestFor) return
    setHv(blankHarvest(harvestFor.crop, harvestFor.id))
    setTimeout(() => form.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50)
  }, [harvestFor])

  const done = (text) => {
    setMsg({ ok: true, text })
    plantings.reload()
    harvests.reload()
    onChange?.()
  }
  const fail = () => setMsg({ ok: false, text: t('crops.saveFailed') })

  const savePlanting = (e) => {
    e.preventDefault()
    addPlanting(fieldId, plant).then(() => { setPlant({ crop: '', planted_on: today() }); done(t('crops.plantSaved')) }).catch(fail)
  }
  const saveHarvest = (e) => {
    e.preventDefault()
    const num = (v) => (v === '' || v == null ? null : Number(v))
    const body = { ...hv, amount_kg: Number(hv.amount_kg), sold_kg: num(hv.sold_kg), area_ha: num(hv.area_ha),
      price_mkd_kg: num(hv.price_mkd_kg), quality: hv.quality || null, notes: hv.notes || null }
    addHarvest(fieldId, body).then(() => { setHv(null); done(t('crops.harvestSaved')) }).catch(fail)
  }

  const active = (plantings.data?.plantings ?? []).filter((p) => !p.harvested_on)
  const rows = harvests.data?.harvests ?? []
  const official = harvests.data?.official_yield_kg_ha ?? {}
  // yield trend for the crop logged most often, where the area was entered
  const main = Object.entries(rows.reduce((m, h) => ({ ...m, [h.crop]: (m[h.crop] ?? 0) + 1 }), {})).sort((a, b) => b[1] - a[1])[0]?.[0]
  const trend = rows.filter((h) => h.crop === main && h.area_ha).map((h) => ({ label: h.harvested_on.slice(0, 4), kgHa: Math.round(h.amount_kg / h.area_ha) }))
  const set = (k) => (e) => setHv({ ...hv, [k]: e.target.value })

  return (
    <article className="card crop-tracker" id="crops">
      <div className="card-head"><h2>{t('crops.title')}</h2></div>
      <p className="chart-help">{t(owner ? 'crops.help' : 'crops.helpDemo')}</p>

      {active.length > 0 && <ul className="plant-list">
        {active.map((p) => (
          <li key={p.id}>
            <div className="plant-top">
              <strong>{cropName(p.crop)}</strong>
              <span className="muted small">{fmt(t('crops.plantedOn'), { date: day(p.planted_on, { day: 'numeric', month: 'short', year: 'numeric' }) })}</span>
            </div>
            {p.progress != null && <>
              <div className="progress" role="img" aria-label={`${Math.round(p.progress * 100)}%`}>
                <span style={{ width: `${Math.min(100, p.progress * 100)}%` }} className={p.status === 'ready' ? 'is-ready' : ''} />
              </div>
              <p className="small muted">
                {fmt(t('crops.gddLine'), { gdd: p.gdd, need: p.gdd_needed, base: p.base_temp_c })}
                {p.expected_harvest && ` · ${fmt(t('crops.expected'), { date: day(p.expected_harvest, { day: 'numeric', month: 'short', year: 'numeric' }) })}`}
              </p>
            </>}
            {owner && <div className="row-btns">
              <button className="btn btn-volt" onClick={() => setHv(blankHarvest(p.crop, p.id))}>{t('summary.enterHarvest')}</button>
              <button className="btn btn-ghost" onClick={() => deletePlanting(fieldId, p.id).then(() => done(t('crops.removed'))).catch(fail)}>{t('crops.remove')}</button>
            </div>}
          </li>
        ))}
      </ul>}

      {owner && <form className="inline-form" onSubmit={savePlanting}>
        <label className="select"><span>{t('crops.crop')}</span>
          <select required value={plant.crop} onChange={(e) => setPlant({ ...plant, crop: e.target.value })}>
            <option value="">—</option>
            {crops.map((c) => <option key={c.id} value={c.id}>{cropName(c.id)}</option>)}
          </select>
        </label>
        <label className="text-input"><span>{t('crops.plantedDate')}</span>
          <input type="date" required max={today()} value={plant.planted_on} onChange={(e) => setPlant({ ...plant, planted_on: e.target.value })} />
        </label>
        <button className="btn">{t('crops.addPlanting')}</button>
      </form>}

      {owner && !hv && <button className="btn btn-ghost spaced" onClick={() => setHv(blankHarvest())}>{t('crops.logHarvest')}</button>}

      {hv && <form className="harvest-form" ref={form} onSubmit={saveHarvest}>
        <h3>{t('summary.enterHarvest')}</h3>
        <div className="form-grid">
          <label className="select"><span>{t('crops.crop')}</span>
            <select required value={hv.crop} onChange={set('crop')}>
              <option value="">—</option>
              {crops.map((c) => <option key={c.id} value={c.id}>{cropName(c.id)}</option>)}
            </select>
          </label>
          <label className="text-input"><span>{t('crops.harvestDate')}</span><input type="date" required max={today()} value={hv.harvested_on} onChange={set('harvested_on')} /></label>
          <label className="text-input"><span>{t('crops.amount')}</span><input type="number" inputMode="decimal" min="0" step="any" required value={hv.amount_kg} onChange={set('amount_kg')} /></label>
          <label className="text-input"><span>{t('crops.sold')}</span><input type="number" inputMode="decimal" min="0" step="any" value={hv.sold_kg} onChange={set('sold_kg')} /></label>
          <label className="text-input"><span>{t('crops.area')}</span><input type="number" inputMode="decimal" min="0" step="any" value={hv.area_ha} onChange={set('area_ha')} /></label>
          <label className="text-input"><span>{t('crops.price')}</span><input type="number" inputMode="decimal" min="0" step="any" value={hv.price_mkd_kg} onChange={set('price_mkd_kg')} /></label>
          <label className="select"><span>{t('crops.quality')}</span>
            <select value={hv.quality} onChange={set('quality')}>
              <option value="">—</option>
              {['good', 'average', 'poor'].map((q) => <option key={q} value={q}>{t(`crops.q_${q}`)}</option>)}
            </select>
          </label>
          <label className="text-input wide"><span>{t('crops.notes')}</span><input maxLength={500} value={hv.notes} onChange={set('notes')} /></label>
        </div>
        <div className="row-btns">
          <button className="btn btn-volt">{t('crops.saveHarvest')}</button>
          <button type="button" className="btn btn-ghost" onClick={() => setHv(null)}>{t('crops.cancel')}</button>
        </div>
      </form>}

      {msg && <p className={`msg ${msg.ok ? 'msg-ok' : 'msg-bad'}`} role="status">{msg.text}</p>}

      {rows.length > 0 && <>
        <h3 className="sub-head">{t('crops.history')}</h3>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>{t('crops.harvestDate')}</th><th>{t('crops.crop')}</th><th>kg</th><th>{t('crops.soldShort')}</th><th>kg/ha</th><th /></tr></thead>
            <tbody>
              {rows.slice().reverse().map((h) => (
                <tr key={h.id}>
                  <td>{day(h.harvested_on, { day: 'numeric', month: 'short', year: 'numeric' })}</td>
                  <td>{cropName(h.crop)}{h.quality && <span className="muted small"> · {t(`crops.q_${h.quality}`)}</span>}</td>
                  <td>{Math.round(h.amount_kg).toLocaleString()}</td>
                  <td>{h.sold_kg == null ? '—' : Math.round(h.sold_kg).toLocaleString()}</td>
                  <td>{h.area_ha ? Math.round(h.amount_kg / h.area_ha).toLocaleString() : '—'}</td>
                  <td>{owner && <button className="link-btn" aria-label={t('crops.remove')} onClick={() => deleteHarvest(fieldId, h.id).then(() => done(t('crops.removed'))).catch(fail)}>✕</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {trend.length > 0 && <>
          <p className="chart-help">{fmt(t('crops.trendHelp'), { crop: cropName(main) })}</p>
          <YieldChart points={trend} official={official[main]?.yield_kg_ha} />
          {official[main] && <p className="source">{harvests.data.official_source} · {official[main].years}</p>}
        </>}
      </>}
    </article>
  )
}
