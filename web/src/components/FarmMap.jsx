import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import '@geoman-io/leaflet-geoman-free'
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css'
import { useEffect, useRef, useState } from 'react'
import { addBasemap } from './basemap.js'

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
  const [name, setName] = useState('New field')
  const [seasons, setSeasons] = useState([['pepper'], ['pepper'], ['tomato']])
  const [irrigation, setIrrigation] = useState('drip')
  const [busy, setBusy] = useState(false)
  const main = crops.filter((c) => !c.cover_crop)
  const setSeason = (i, v) => setSeasons(seasons.map((s, k) => (k === i ? [v] : s)))
  return (
    <form className="draw-form card" onSubmit={async (e) => {
      e.preventDefault(); setBusy(true)
      try { await onSave({ name, current_rotation: seasons, irrigation }) } finally { setBusy(false) }
    }}>
      <h3>New field · {draft.area.toFixed(2)} ha</h3>
      <label>Name<input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} required /></label>
      <fieldset>
        <legend>What it grows now (one crop per season)</legend>
        <div className="season-pick">
          {seasons.map((s, i) => (
            <select key={i} value={s[0]} onChange={(e) => setSeason(i, e.target.value)} aria-label={`Season ${i + 1}`}>
              {main.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          ))}
          {seasons.length < 5 && <button type="button" className="btn btn-ghost" onClick={() => setSeasons([...seasons, [seasons[0][0]]])}>+ season</button>}
          {seasons.length > 1 && <button type="button" className="btn btn-ghost" onClick={() => setSeasons(seasons.slice(0, -1))}>−</button>}
        </div>
      </fieldset>
      <label>Irrigation
        <select value={irrigation} onChange={(e) => setIrrigation(e.target.value)}>
          <option value="drip">Drip</option><option value="sprinkler">Sprinkler</option>
          <option value="furrow">Furrow</option><option value="none">None (rain-fed)</option>
        </select>
      </label>
      <div className="row-actions">
        <button className="btn btn-volt" disabled={busy}>{busy ? 'Saving…' : 'Save field'}</button>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}

export default function FarmMap({ fields, selectedId, onSelect, onCreate, crops }) {
  const box = useRef(null)
  const map = useRef(null)
  const layer = useRef(null)
  const fitted = useRef(false) // id of the field the map last zoomed to
  const [drawing, setDrawing] = useState(false)
  const [draft, setDraft] = useState(null)

  useEffect(() => {
    const m = L.map(box.current, { zoomControl: true, scrollWheelZoom: false, maxZoom: 19 })
    addBasemap(m, 'satellite')
    m.setView([41.4145, 22.7274], 14)
    layer.current = L.layerGroup().addTo(m)
    m.pm.setGlobalOptions({ pathOptions: { color: '#fff100', weight: 2 } })
    m.on('pm:create', (e) => {
      const ll = e.layer.getLatLngs()[0]
      e.layer.remove()
      setDrawing(false)
      setDraft({ polygon: ll.map((p) => [+p.lat.toFixed(6), +p.lng.toFixed(6)]), area: areaHa(ll) })
    })
    map.current = m
    fitted.current = false // a new map (React may mount twice in development) must zoom again
    return () => { m.remove(); map.current = null }
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

  const startDraw = () => {
    setDraft(null)
    setDrawing(true)
    map.current.pm.enableDraw('Polygon', { snappable: false, finishOn: 'dblclick' })
  }
  const cancelDraw = () => {
    map.current.pm.disableDraw()
    setDrawing(false)
  }

  return (
    <section className="card map-card">
      <div className="map-head">
        <div>
          <p className="eyebrow">Your farm</p>
          <h2>Select a field</h2>
        </div>
        {drawing
          ? <button className="btn btn-ghost" onClick={cancelDraw}>Cancel drawing</button>
          : <button className="btn" onClick={startDraw}>Draw a field</button>}
      </div>
      {drawing && <p className="muted small">Click each corner of the field on the photo; click the first corner again to finish.</p>}
      <div className="map-wrap">
        <div ref={box} className="farm-map" role="application" aria-label="Farm map" />
        {draft && (
          <NewFieldForm draft={draft} crops={crops}
            onCancel={() => setDraft(null)}
            onSave={async (body) => { await onCreate({ ...body, polygon: draft.polygon }); setDraft(null) }} />
        )}
      </div>
      <div className="field-chips">
        {fields.map((f) => (
          <button key={f.id} className={`chip ${String(f.id) === String(selectedId) ? 'is-sel' : ''}`} onClick={() => onSelect(f.id)}>
            {f.name} <small>{f.area_ha} ha</small>
          </button>
        ))}
      </div>
    </section>
  )
}
