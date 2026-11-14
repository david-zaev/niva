import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { DEMO_FIELD, fieldId as currentField, getFields, isOwner, myFieldIds, paths, peek, saveOutline, switchField } from '../api.js'
import Screen from '../components/Screen.jsx'
import TermHelp from '../components/TermHelp.jsx'
import { addBasemap, hectares } from '../components/basemap.js'
import { fmt, useCrops } from '../components/util.js'
import { useI18n } from '../i18n/index.jsx'

const ago = (days) => new Date(Date.now() - days * 86400000).toISOString().slice(0, 10)
// NASA GIBS WMTS layers (no key). Each layer's newest complete day is a few days back.
const GIBS = [
  { id: 'smap', layer: 'SMAP_L4_Analyzed_Surface_Soil_Moisture', level: 6, date: ago(4), name: 'NASA SMAP L4 surface soil moisture, 9 km' },
  { id: 'ndvi', layer: 'MODIS_Terra_NDVI_8Day', level: 9, date: ago(12), name: 'NASA MODIS Terra NDVI, 8-day, 250 m' },
  { id: 'lst', layer: 'MODIS_Terra_Land_Surface_Temp_Day', level: 7, date: ago(2), name: 'NASA MODIS Terra land surface temperature (day), 1 km' },
  { id: 'rain', layer: 'IMERG_Precipitation_Rate', level: 6, date: ago(1), name: 'NASA GPM IMERG precipitation rate, 0.1°' },
]
const gibsUrl = (g) => `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${g.layer}/default/${g.date}/GoogleMapsCompatible_Level${g.level}/{z}/{y}/{x}.png`
const VOLT = '#fff100'

export default function Fields() {
  const { t } = useI18n()
  const { cropName } = useCrops()
  const box = useRef(null)
  const map = useRef(null)
  const shapes = useRef(null)
  const overlay = useRef(null)
  const farmland = useRef(null)
  const draft = useRef(null)
  const [fields, setFields] = useState(() => peek(paths.fields(myFieldIds()))?.fields ?? [])
  const [selected, setSelected] = useState(currentField())
  const [showAll, setShowAll] = useState(false)
  const [layer, setLayer] = useState(null)
  const [base, setBase] = useState('satellite')
  const baseLayer = useRef(null)
  const [drawing, setDrawing] = useState(false)
  const [points, setPoints] = useState([])
  const [msg, setMsg] = useState(null)
  const [query, setQuery] = useState('')
  const [places, setPlaces] = useState([])
  const owner = isOwner(selected)
  const active = fields.find((f) => String(f.id) === String(selected))
  const label = (f) => (String(f.id) === DEMO_FIELD ? t('switcher.demo') : f.name)

  const reload = () => getFields().then((d) => setFields(d.fields)).catch(() => setMsg({ ok: false, text: t('server.down') }))
  useEffect(() => { reload() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // map once
  useEffect(() => {
    const m = L.map(box.current, { center: [41.6, 21.75], zoom: 8 })
    shapes.current = L.layerGroup().addTo(m)
    farmland.current = L.layerGroup().addTo(m)
    draft.current = L.layerGroup().addTo(m)
    map.current = m
    return () => m.remove()
  }, [])

  // base map: satellite by default, street map on request
  useEffect(() => {
    if (!map.current) return
    baseLayer.current?.remove()
    baseLayer.current = addBasemap(map.current, base)
  }, [base])

  // drawing: each tap adds a corner
  useEffect(() => {
    const m = map.current
    if (!m || !drawing) return
    const add = (e) => setPoints((p) => [...p, [+e.latlng.lat.toFixed(6), +e.latlng.lng.toFixed(6)]])
    m.on('click', add)
    return () => m.off('click', add)
  }, [drawing])
  useEffect(() => {
    draft.current?.clearLayers()
    if (points.length) L.polygon(points, { color: '#000', weight: 2, dashArray: '5 5', fillColor: VOLT, fillOpacity: 0.35 }).addTo(draft.current)
    points.forEach((p) => L.circleMarker(p, { radius: 4, color: '#000', weight: 2, fillColor: VOLT, fillOpacity: 1 }).addTo(draft.current))
  }, [points])

  // fields: the selected one in volt and thick, the others quiet; labels with name and crop
  useEffect(() => {
    const m = map.current
    if (!m) return
    shapes.current.clearLayers()
    const bounds = []
    fields.forEach((f) => {
      const on = String(f.id) === String(selected)
      if (!on && !showAll) return
      const style = on ? { color: '#000', weight: 3, fillColor: VOLT, fillOpacity: 0.55 } : { color: '#444', weight: 2, fillColor: '#ffffff', fillOpacity: 0.5 }
      const shape = f.polygon?.length >= 3 ? L.polygon(f.polygon, style) : L.circleMarker([f.lat, f.lon], { ...style, radius: on ? 11 : 8, fillOpacity: 1 })
      shape.bindTooltip(`${label(f)}${f.active_crop ? ` · ${cropName(f.active_crop)}` : ''}`, { permanent: true, direction: 'top', className: on ? 'map-label is-on' : 'map-label', offset: [0, -8] })
      shape.on('click', () => { if (!drawing) { switchField(f.id); setSelected(String(f.id)) } })
      shape.addTo(shapes.current)
      if (f.polygon?.length >= 3) bounds.push(...f.polygon)
      else bounds.push([f.lat, f.lon])
      if (on && !showAll) m.setView(f.polygon?.length >= 3 ? L.polygon(f.polygon).getBounds().getCenter() : [f.lat, f.lon], 15)
    })
    if (showAll && bounds.length) m.fitBounds(L.latLngBounds(bounds).pad(0.3), { maxZoom: 14 })
  }, [fields, selected, showAll, drawing]) // eslint-disable-line react-hooks/exhaustive-deps

  // NASA overlay
  useEffect(() => {
    overlay.current?.remove()
    overlay.current = null
    const g = GIBS.find((x) => x.id === layer)
    if (g && map.current) overlay.current = L.tileLayer(gibsUrl(g), { maxNativeZoom: g.level, maxZoom: 19, opacity: 0.65, attribution: 'NASA GIBS' }).addTo(map.current)
  }, [layer])

  const findFarmland = async () => {
    const m = map.current
    if (m.getZoom() < 14) return setMsg({ ok: false, text: t('map.zoomIn') })
    const b = m.getBounds()
    const q = `[out:json][timeout:25];way["landuse"~"^(farmland|orchard|vineyard|greenhouse_horticulture)$"](${b.getSouth()},${b.getWest()},${b.getNorth()},${b.getEast()});out geom 200;`
    setMsg({ ok: true, text: t('map.searching') })
    try {
      const res = await fetch('https://overpass-api.de/api/interpreter', { method: 'POST', body: new URLSearchParams({ data: q }) })
      const d = await res.json()
      farmland.current.clearLayers()
      d.elements.filter((w) => w.geometry?.length >= 3).forEach((w) => {
        const poly = w.geometry.map((p) => [+p.lat.toFixed(6), +p.lon.toFixed(6)])
        L.polygon(poly, { color: '#1a9b4b', weight: 1.5, fillOpacity: 0.12 })
          .on('click', () => { if (owner) { setPoints(poly); setDrawing(false); setMsg({ ok: true, text: t('map.picked') }) } })
          .addTo(farmland.current)
      })
      setMsg({ ok: true, text: fmt(t('map.found'), { n: d.elements.length }) })
    } catch {
      setMsg({ ok: false, text: t('map.osmDown') })
    }
  }

  const search = async (e) => {
    e.preventDefault()
    if (!query.trim()) return
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&countrycodes=mk&limit=6&q=${encodeURIComponent(query.trim())}`)
      setPlaces(await res.json())
    } catch {
      setPlaces([])
    }
  }

  const save = () => saveOutline(selected, points)
    .then(() => { setPoints([]); setDrawing(false); setMsg({ ok: true, text: t('map.saved') }); reload() })
    .catch(() => setMsg({ ok: false, text: t('crops.saveFailed') }))

  const g = GIBS.find((x) => x.id === layer)
  return (
    <Screen section="map" eyebrow={active ? label(active) : undefined}
      actions={<button className="btn btn-ghost" aria-pressed={showAll} onClick={() => setShowAll(!showAll)}>{showAll ? t('map.onlyThis') : t('map.showAll')}</button>}>
      <div className="map-tools">
        <div className="segmented layer-toggle" role="group" aria-label={t('map.base')}>
          <button aria-pressed={base === 'satellite'} onClick={() => setBase('satellite')}>{t('map.satellite')}</button>
          <button aria-pressed={base === 'street'} onClick={() => setBase('street')}>{t('map.street')}</button>
        </div>
        <div className="segmented layer-toggle" role="group" aria-label={t('map.layers')}>
          <button aria-pressed={layer == null} onClick={() => setLayer(null)}>{t('map.none')}</button>
          {GIBS.map((x) => <button key={x.id} aria-pressed={layer === x.id} onClick={() => setLayer(x.id)}>{t(`map.l_${x.id}`)}</button>)}
        </div>
        <form className="place-search" onSubmit={search}>
          <input className="search-input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('map.searchPlaceholder')} aria-label={t('map.searchPlaceholder')} />
          <button className="btn">{t('map.search')}</button>
        </form>
      </div>
      {places.length > 0 && <ul className="place-results">
        {places.map((p) => <li key={p.place_id}><button className="link-btn" onClick={() => { map.current.setView([+p.lat, +p.lon], 15); setPlaces([]) }}>{p.display_name}</button></li>)}
      </ul>}

      <div className="card map-card">
        <div ref={box} className="map map-big" role="application" aria-label={t('map.title')} />
        {g && <p className="source">{g.name} · {g.date} · NASA GIBS / Worldview <TermHelp term={`layer_${g.id}`} /></p>}
      </div>

      <article className="card">
        <div className="card-head"><h2>{t('map.outlineTitle')}</h2></div>
        {owner
          ? <>
              <p className="chart-help">{t('map.outlineHelp')}</p>
              <div className="row-btns">
                <button className="btn" aria-pressed={drawing} onClick={() => { setDrawing(!drawing); if (!drawing) setPoints([]) }}>{drawing ? t('map.stopDrawing') : t('map.draw')}</button>
                <button className="btn btn-ghost" onClick={findFarmland}>{t('map.findFarmland')}</button>
                {points.length > 0 && <button className="btn btn-ghost" onClick={() => setPoints((p) => p.slice(0, -1))}>{t('map.undo')}</button>}
                {points.length >= 3 && <button className="btn btn-volt" onClick={save}>{fmt(t('map.saveOutline'), { n: points.length })}</button>}
                {points.length > 0 && <button className="btn btn-ghost" onClick={() => setPoints([])}>{t('map.clear')}</button>}
                {active?.polygon?.length >= 3 && <button className="btn btn-ghost" onClick={() => { setPoints([]); saveOutline(selected, []).then(reload) }}>{t('map.removeOutline')}</button>}
              </div>
            </>
          : <p className="chart-help">{t('map.viewOnly')} <Link to="/setup">{t('more.newField')}</Link></p>}
        {points.length >= 3 && <p className="area-readout">{fmt(t('map.area'), { ha: hectares(points).toFixed(2) })}</p>}
        {!drawing && active?.polygon?.length >= 3 && <p className="area-readout">{fmt(t('map.area'), { ha: hectares(active.polygon).toFixed(2) })}</p>}
        {msg && <p className={`msg ${msg.ok ? 'msg-ok' : 'msg-bad'}`} role="status">{msg.text}</p>}
        <p className="note">{t('map.cadastre')} <a href="https://e-uslugi.katastar.gov.mk/katastarskiPlanovi" target="_blank" rel="noreferrer">{t('map.cadastreLink')} ↗</a></p>
      </article>

      <ul className="field-list">
        {fields.map((f) => (
          <li key={f.id}>
            <button className={`field-row ${String(f.id) === String(selected) ? 'is-on' : ''}`} onClick={() => { switchField(f.id); setSelected(String(f.id)); setShowAll(false) }}>
              <strong>{label(f)}</strong>
              <span className="muted small">{f.active_crop ? cropName(f.active_crop) : t('switcher.noCrop')} · {f.lat.toFixed(3)}, {f.lon.toFixed(3)}{f.polygon?.length >= 3 ? ` · ${t('map.hasOutline')}` : ''}</span>
            </button>
          </li>
        ))}
        <li><Link className="btn btn-volt" to="/setup">+ {t('switcher.add')}</Link></li>
      </ul>
    </Screen>
  )
}
