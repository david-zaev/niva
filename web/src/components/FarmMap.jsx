import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import '@geoman-io/leaflet-geoman-free'
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css'
import { useEffect, useRef, useState } from 'react'
import { addBasemap } from './basemap.js'
import { useI18n } from '../i18n/index.jsx'

function areaHa(latlngs) {
  if (latlngs.length < 3) return 0
  const lat0 = latlngs.reduce((a, p) => a + p.lat, 0) / latlngs.length
  const k = 111320
  const pts = latlngs.map((p) => [p.lng * k * Math.cos((lat0 * Math.PI) / 180), p.lat * k])
  let s = 0
  for (let i = 0; i < pts.length; i++) {
    const [x1, y1] = pts[(i + pts.length - 1) % pts.length]
    const [x2, y2] = pts[i]
    s += x1 * y2 - x2 * y1
  }
  return Math.abs(s) / 2 / 10000
}

function NewFieldForm({ draft, crops, onSave, onCancel }) {
  const { t, lang } = useI18n()
  const [name, setName] = useState(() => t('app.map.defaultName'))
  const [known, setKnown] = useState(false)
  const [seasons, setSeasons] = useState([['pepper'], ['pepper'], ['tomato']])
  const [irrigation, setIrrigation] = useState('drip')
  const [busy, setBusy] = useState(false)
  const main = crops.filter((c) => !c.cover_crop)
  const setSeason = (i, v) => setSeasons(seasons.map((s, k) => (k === i ? [v] : s)))
  return (
    <form className="draw-form card" onSubmit={async (e) => {
      e.preventDefault(); setBusy(true)
      try { await onSave({ name, current_rotation: known ? seasons : [], irrigation }) } finally { setBusy(false) }
    }}>
      <h3>{t('app.map.newField', { ha: draft.area.toFixed(2) })}</h3>
      <label>{t('app.map.name')}<input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} required /></label>
      <label className="check-line">
        <input type="checkbox" checked={known} onChange={(e) => setKnown(e.target.checked)} />
        <span>{t('app.map.growsOptional')}<small>{t('app.map.growsHelp')}</small></span>
      </label>
      {known && <fieldset>
        <legend>{t('app.map.grows')}</legend>
        <div className="season-pick">
          {seasons.map((s, i) => (
            <select key={i} value={s[0]} onChange={(e) => setSeason(i, e.target.value)} aria-label={t('app.map.season', { n: i + 1 })}>
              {main.map((c) => <option key={c.id} value={c.id}>{lang === 'mk' && c.name_mk ? c.name_mk : c.name}</option>)}
            </select>
          ))}
          {seasons.length < 5 && <button type="button" className="btn btn-ghost" onClick={() => setSeasons([...seasons, [seasons[0][0]]])}>{t('app.map.addSeason')}</button>}
          {seasons.length > 1 && <button type="button" className="btn btn-ghost" onClick={() => setSeasons(seasons.slice(0, -1))} aria-label={t('app.map.removeSeason')}>−</button>}
        </div>
      </fieldset>}
      <label>{t('app.map.irrigation')}
        <select value={irrigation} onChange={(e) => setIrrigation(e.target.value)}>
          {['drip', 'sprinkler', 'furrow', 'none'].map((k) => <option key={k} value={k}>{t(`app.map.${k}`)}</option>)}
        </select>
      </label>
      <div className="row-actions">
        <button className="btn btn-volt" disabled={busy}>{busy ? t('app.map.saving') : t('app.map.save')}</button>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>{t('app.map.cancel')}</button>
      </div>
    </form>
  )
}

// Place search on the map (OpenStreetMap Nominatim): only on submit, as its usage policy asks
function PlaceSearch({ onPick }) {
  const { t, lang } = useI18n()
  const [q, setQ] = useState('')
  const [hits, setHits] = useState(null)
  const [busy, setBusy] = useState(false)
  const search = async (e) => {
    e.preventDefault()
    const text = q.trim()
    if (text.length < 2) return
    setBusy(true)
    try {
      const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=6&accept-language=${lang === 'mk' ? 'mk,en' : 'en'}&q=${encodeURIComponent(text)}`
      const res = await fetch(url, { headers: { Accept: 'application/json' } })
      setHits(res.ok ? await res.json() : [])
    } catch {
      setHits([])
    } finally {
      setBusy(false)
    }
  }
  const pick = (h) => {
    const [s, n, w, e] = h.boundingbox.map(Number)
    onPick([[s, w], [n, e]], [Number(h.lat), Number(h.lon)])
    setHits(null)
  }
  return (
    <div className="place-search">
      <form role="search" onSubmit={search}>
        <input type="search" value={q} onChange={(e) => { setQ(e.target.value); if (!e.target.value) setHits(null) }}
          placeholder={t('app.map.searchPh')} aria-label={t('app.map.searchLabel')} />
        <button className="btn btn-map" disabled={busy}>{busy ? '…' : t('app.map.search')}</button>
      </form>
      {hits && (
        <ul className="place-hits">
          {hits.length === 0 && <li className="muted small">{t('app.map.noPlace')}</li>}
          {hits.map((h) => (
            <li key={h.place_id}>
              <button type="button" onClick={() => pick(h)}>
                <b>{h.name || h.display_name.split(',')[0]}</b>
                <small>{h.display_name}</small>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function FarmMap({ fields, selectedId, onSelect, onCreate, onDelete, crops }) {
  const { t } = useI18n()
  const box = useRef(null)
  const map = useRef(null)
  const layer = useRef(null)
  const fitted = useRef(false) // id of the field the map last zoomed to
  const [drawing, setDrawing] = useState(false)
  const [draft, setDraft] = useState(null)
  const draftLayer = useRef(null) // the outline just drawn, shown until it is saved or cancelled
  const [deleting, setDeleting] = useState(false)
  const card = useRef(null)
  const [full, setFull] = useState(false)
  const canFull = typeof document !== 'undefined' && !!document.fullscreenEnabled
  useEffect(() => {
    // Leaflet must re-measure when the card grows to the whole screen and back
    const onChange = () => {
      setFull(document.fullscreenElement === card.current)
      requestAnimationFrame(() => map.current?.invalidateSize())
    }
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])
  const toggleFull = () => (document.fullscreenElement ? document.exitFullscreen() : card.current.requestFullscreen()).catch(() => {})
  const selected = fields.find((f) => String(f.id) === String(selectedId))
  const removeSelected = async () => {
    if (!selected || !window.confirm(t('app.map.confirmDelete', { name: selected.name }))) return
    setDeleting(true)
    try { await onDelete(selected.id) } finally { setDeleting(false) }
  }

  useEffect(() => {
    const m = L.map(box.current, { zoomControl: false, scrollWheelZoom: false, maxZoom: 19 })
    addBasemap(m, 'satellite')
    L.control.zoom({ position: 'bottomright' }).addTo(m)
    m.setView([41.4145, 22.7274], 14)
    layer.current = L.layerGroup().addTo(m)
    m.pm.setGlobalOptions({ pathOptions: { color: '#fff100', weight: 2 } })
    m.on('pm:create', (e) => {
      const ll = e.layer.getLatLngs()[0]
      draftLayer.current?.remove()
      e.layer.setStyle({ color: '#fff100', weight: 3, dashArray: '6 6', fillColor: '#fff100', fillOpacity: 0.25 })
      draftLayer.current = e.layer
      // keep the outline in view beside the form (right on a wide screen, above the sheet on a phone)
      const narrow = m.getContainer().clientWidth < 600
      const h = m.getContainer().clientHeight
      m.fitBounds(e.layer.getBounds(), {
        paddingTopLeft: [24, narrow ? 120 : 80],
        paddingBottomRight: narrow ? [24, Math.round(h * 0.55)] : [400, 24],
        maxZoom: 18,
      })
      setDrawing(false)
      setDraft({ polygon: ll.map((p) => [+p.lat.toFixed(6), +p.lng.toFixed(6)]), area: areaHa(ll) })
    })
    // Alt + scroll wheel zooms the map; a plain scroll keeps scrolling the page
    const el = box.current
    let last = -Infinity
    const onWheel = (e) => {
      if (!e.altKey || e.deltaY === 0) return
      e.preventDefault()
      e.stopPropagation()
      const now = Date.now()
      if (now - last < 300) return // let Leaflet's 250 ms zoom transition finish between steps
      const zoom = Math.max(m.getMinZoom(), Math.min(m.getMaxZoom(), m.getZoom() + (e.deltaY < 0 ? 1 : -1)))
      if (zoom === m.getZoom()) return
      last = now
      m.stop()
      m.setZoomAround(m.mouseEventToContainerPoint(e), zoom, { animate: true })
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    map.current = m
    fitted.current = false // a new map (React may mount twice in development) must zoom again
    return () => { el.removeEventListener('wheel', onWheel); draftLayer.current = null; m.remove(); map.current = null }
  }, [])

  useEffect(() => {
    const m = map.current
    if (!m) return
    layer.current.clearLayers()
    const bounds = []
    for (const f of fields) {
      if (!f.polygon?.length) continue
      const sel = String(f.id) === String(selectedId)
      const poly = L.polygon(f.polygon, {
        color: sel ? '#fff100' : '#ffffff', weight: sel ? 3 : 2, fillOpacity: sel ? 0.25 : 0.08,
        fillColor: sel ? '#fff100' : '#ffffff',
      })
      poly.bindTooltip(`${f.name} · ${f.area_ha} ha`, { permanent: true, direction: 'center', className: `field-label${sel ? ' is-sel' : ''}` })
      poly.on('click', () => onSelect(f.id))
      poly.addTo(layer.current)
      bounds.push(...f.polygon)
      if (sel && fitted.current !== f.id) {
        // zoom to the selected field with some of its surroundings
        const animate = fitted.current !== false
        const b = poly.getBounds()
        fitted.current = f.id
        // after layout: Leaflet must know the container's real size to pick the zoom
        requestAnimationFrame(() => {
          if (map.current !== m) return // that map was removed meanwhile
          m.invalidateSize()
          m.fitBounds(b, { padding: [120, 120], maxZoom: 17, animate })
        })
      }
    }
  }, [fields, selectedId, onSelect])

  useEffect(() => {
    if (!draft && draftLayer.current) {
      draftLayer.current.remove()
      draftLayer.current = null
    }
  }, [draft])

  const startDraw = () => {
    setDraft(null)
    setDrawing(true)
    map.current.pm.enableDraw('Polygon', { snappable: false, finishOn: 'dblclick' })
  }
  const cancelDraw = () => {
    map.current.pm.disableDraw()
    setDrawing(false)
  }

  const hint = drawing ? t('app.map.drawHint') : !fields.length && !draft ? t('app.map.noFields') : null
  return (
    <section ref={card} className="map-card" aria-label={t('app.map.eyebrow')}>
      <div ref={box} className="farm-map" role="application" aria-label={t('app.map.mapLabel')} />
      <div className="map-top">
        <PlaceSearch onPick={(bounds, center) => {
          const m = map.current
          if (!m) return
          const [[s, w], [n, e]] = bounds
          // villages come with a large box: never zoom out further than a view where fields are visible
          if (Math.abs(n - s) > 0.05 || Math.abs(e - w) > 0.05) m.flyTo(center, 15)
          else m.flyToBounds(bounds, { maxZoom: 17 })
        }} />
        <div className="map-actions">
          {selected && !drawing && (
            <button className="btn btn-map btn-danger" disabled={deleting} onClick={removeSelected}>{deleting ? t('app.map.deleting') : t('app.map.delete')}</button>
          )}
          {drawing
            ? <button className="btn btn-map" onClick={cancelDraw}>{t('app.map.cancelDraw')}</button>
            : <button className="btn btn-volt" onClick={startDraw}>{t('app.map.drawBtn')}</button>}
          {canFull && (
            <button type="button" className="btn btn-map btn-icon btn-full" onClick={toggleFull}
              aria-label={full ? t('app.map.exitFullscreen') : t('app.map.fullscreen')} title={full ? t('app.map.exitFullscreen') : t('app.map.fullscreen')}>
              <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                {full
                  ? <path d="M8 3v5H3M12 3v5h5M8 17v-5H3M12 17v-5h5" />
                  : <path d="M3 8V3h5M17 8V3h-5M3 12v5h5M17 12v5h-5" />}
              </svg>
            </button>
          )}
        </div>
      </div>
      {hint && <p className="map-hint">{hint}</p>}
      {fields.length > 0 && !draft && (
        <div className="field-chips">
          {fields.map((f) => (
            <button key={f.id} className={`chip ${String(f.id) === String(selectedId) ? 'is-sel' : ''}`} onClick={() => onSelect(f.id)}>
              {f.name} <small>{f.area_ha} ha</small>
            </button>
          ))}
        </div>
      )}
      {draft && (
        <NewFieldForm draft={draft} crops={crops}
          onCancel={() => setDraft(null)}
          onSave={async (body) => { await onCreate({ ...body, polygon: draft.polygon }); setDraft(null) }} />
      )}
    </section>
  )
}
