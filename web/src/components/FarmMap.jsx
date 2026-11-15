import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import '@geoman-io/leaflet-geoman-free'
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css'
import { useEffect, useRef, useState } from 'react'
import { addBasemap } from './basemap.js'
import { useI18n } from '../i18n/index.jsx'
import border from './mkBorder.json'

// Niva's prices, sowing dates and plant rules are Macedonian: the map shows and accepts only North Macedonia
const MK = border.ring_lat_lon
const MK_BOUNDS = L.latLngBounds(MK).pad(0.08)
function inMK([lat, lng]) {
  let hit = false
  for (let i = 0, j = MK.length - 1; i < MK.length; j = i++) {
    const [y1, x1] = MK[j]
    const [y2, x2] = MK[i]
    if ((y1 > lat) !== (y2 > lat) && lng < x1 + ((lat - y1) * (x2 - x1)) / (y2 - y1)) hit = !hit
  }
  return hit
}

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

// The form beside the map, for a field just drawn (no `field`) or one being edited (`field`)
function FieldForm({ field, area, crops, blocked, onSave, onCancel }) {
  const { t, lang } = useI18n()
  const isCover = (id) => crops.find((c) => c.id === id)?.cover_crop
  const had = field?.current_rotation?.length
    ? field.current_rotation.map((s) => [s.find((c) => !isCover(c)) ?? s[0]]) : null
  const [name, setName] = useState(() => field?.name ?? t('app.map.defaultName'))
  const [known, setKnown] = useState(!!had)
  const [seasons, setSeasons] = useState(had ?? [['pepper'], ['pepper'], ['tomato']])
  const [irrigation, setIrrigation] = useState(field?.irrigation ?? 'drip')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const main = crops.filter((c) => !c.cover_crop)
  const setSeason = (i, v) => setSeasons(seasons.map((s, k) => (k === i ? [v] : s)))
  return (
    <form className="draw-form card" onSubmit={async (e) => {
      e.preventDefault(); setBusy(true); setError(null)
      try { await onSave({ name, current_rotation: known ? seasons : [], irrigation }) } catch (x) { setError(x.message) } finally { setBusy(false) }
    }}>
      <h3>{t(field ? 'app.map.editField' : 'app.map.newField', { ha: area.toFixed(2) })}</h3>
      {field && <p className="muted small">{t('app.map.editHint')}</p>}
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
        <button className="btn btn-volt" disabled={busy || blocked}>{busy ? t('app.map.saving') : t(field ? 'app.map.saveChanges' : 'app.map.save')}</button>
        <button type="button" className="btn btn-ghost" onClick={onCancel}>{t('app.map.cancel')}</button>
      </div>
      {error && <p className="error small" role="alert">{error}</p>}
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
      const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=6&countrycodes=mk&accept-language=${lang === 'mk' ? 'mk,en' : 'en'}&q=${encodeURIComponent(text)}`
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

export default function FarmMap({ fields, selectedId, onSelect, onCreate, onUpdate, onDelete, crops }) {
  const { t } = useI18n()
  const box = useRef(null)
  const map = useRef(null)
  const layer = useRef(null)
  const fitted = useRef(false) // id of the field the map last zoomed to
  const [drawing, setDrawing] = useState(false)
  const [draft, setDraft] = useState(null)
  const draftLayer = useRef(null) // the outline just drawn, shown until it is saved or cancelled
  const [deleting, setDeleting] = useState(false)
  const [outside, setOutside] = useState(false)
  const polys = useRef({}) // field id -> its outline on the map
  const [editing, setEditing] = useState(null) // { id, area, inside, changed } while a field is being edited
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
  // asked in the page, not with window.confirm: embedded browsers (app panes, some in-app browsers) silently
  // answer "no" to it, so Delete did nothing there
  const [askDelete, setAskDelete] = useState(false)
  const [deleteError, setDeleteError] = useState(null)
  useEffect(() => { setAskDelete(false); setDeleteError(null) }, [selectedId])
  const removeSelected = async () => {
    if (!selected) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await onDelete(selected.id)
      setAskDelete(false)
    } catch (e) {
      setDeleteError(e.message)
    } finally {
      setDeleting(false)
    }
  }

  useEffect(() => {
    const m = L.map(box.current, {
      zoomControl: false, scrollWheelZoom: false, maxZoom: 19,
      minZoom: 8, maxBounds: MK_BOUNDS, maxBoundsViscosity: 1,
    })
    addBasemap(m, 'satellite')
    L.control.zoom({ position: 'bottomright' }).addTo(m)
    m.setView([41.4145, 22.7274], 14)
    // everything outside the border is dimmed: one big polygon with the country cut out as a hole.
    // Its own renderer draws 3 screens around the view (padding 1.5), so a long drag never shows an undimmed strip
    // before Leaflet redraws at the end of the move.
    const maskRenderer = L.svg({ padding: 1.5 })
    L.polygon([[[90, -180], [90, 180], [-90, 180], [-90, -180]], MK], {
      renderer: maskRenderer, stroke: false, fillColor: '#0b0d0c', fillOpacity: 0.72, interactive: false,
    }).addTo(m)
    L.polygon(MK, { renderer: maskRenderer, color: '#fff100', weight: 1.25, opacity: 0.85, fill: false, interactive: false }).addTo(m)
    layer.current = L.layerGroup().addTo(m)
    m.pm.setGlobalOptions({ pathOptions: { color: '#fff100', weight: 2 } })
    m.on('pm:create', (e) => {
      const ll = e.layer.getLatLngs()[0]
      draftLayer.current?.remove()
      if (!ll.every((p) => inMK([p.lat, p.lng]))) {
        e.layer.remove()
        setDrawing(false)
        setOutside(true)
        return
      }
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
    polys.current = {}
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
      polys.current[f.id] = poly
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

  // edit the selected field: its corners become draggable and the form shows its name, crops and irrigation
  const startEdit = () => {
    const poly = polys.current[selected.id]
    if (!poly) return
    const id = selected.id
    const sync = (changed) => {
      const ll = poly.getLatLngs()[0]
      setEditing((e) => ({ id, area: areaHa(ll), inside: ll.every((p) => inMK([p.lat, p.lng])), changed: changed || !!e?.changed }))
    }
    poly.pm.enable({ snappable: false, allowSelfIntersection: false, draggable: false })
    poly.on('pm:markerdrag pm:edit', () => sync(true))
    poly.closeTooltip()
    sync(false)
  }
  const stopEdit = (revert) => {
    const poly = polys.current[editing?.id]
    if (poly) {
      poly.pm.disable()
      poly.off('pm:markerdrag pm:edit')
      const f = fields.find((x) => x.id === editing.id)
      if (revert && f) poly.setLatLngs(f.polygon)
      poly.openTooltip()
    }
    setEditing(null)
  }
  // another field picked while editing: drop the unsaved changes
  useEffect(() => {
    if (editing && String(editing.id) !== String(selectedId)) stopEdit(true)
  }, [selectedId]) // eslint-disable-line react-hooks/exhaustive-deps

  const startDraw = () => {
    setOutside(false)
    setDraft(null)
    setDrawing(true)
    const m = map.current
    m.pm.enableDraw('Polygon', { snappable: false, finishOn: 'dblclick' })
    // "magnet": with 3+ corners placed, hovering near the first corner pulls the guide line onto it and pulses the
    // corner, so one click closes the field. Geoman finishes the shape when a click lands on the first corner.
    const draw = m.pm.Draw.Polygon
    let on = false
    const set = (near, first) => {
      if (near === on) return
      on = near
      first?.getElement()?.classList.toggle('is-magnet', near)
      draw._hintline?.setStyle({ dashArray: near ? null : '5,5' })
      m.getContainer().classList.toggle('is-closing', near)
      // a "snapped" hint keeps its position on click, and a click at the first corner closes the shape
      if (draw._hintMarker) draw._hintMarker._snapped = near
    }
    const onMove = (e) => {
      const first = draw._markers?.[0]
      if (!first || draw._markers.length < 3) return set(false, first)
      const near = m.latLngToContainerPoint(first.getLatLng()).distanceTo(e.containerPoint) < 22
      set(near, first)
      if (near) draw._hintMarker.setLatLng(first.getLatLng()) // the hint line follows the hint marker
    }
    const stop = () => { set(false, draw._markers?.[0]); m.off('mousemove', onMove); m.off('pm:drawend', stop) }
    m.on('mousemove', onMove) // after Geoman's own handler, so the snap wins
    m.on('pm:drawend', stop)
  }
  const cancelDraw = () => {
    map.current.pm.disableDraw()
    setDrawing(false)
  }

  const hint = (editing && !editing.inside) || outside ? t('app.map.outside') : drawing ? t('app.map.drawHint') : !fields.length && !draft ? t('app.map.noFields') : null
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
          {selected?.demo && !drawing && !draft && (
            <span className="map-tag" title={t('app.map.demoHint')}>{t('app.map.demoField')}</span>
          )}
          {selected && !selected.demo && !drawing && !editing && !draft && !askDelete && (<>
            <button className="btn btn-map btn-danger" onClick={() => setAskDelete(true)}>{t('app.map.delete')}</button>
            <button className="btn btn-map" onClick={startEdit}>{t('app.map.edit')}</button>
          </>)}
          {editing ? null : drawing
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
      {askDelete && selected ? (
        <div className="map-hint confirm-bar" role="alertdialog" aria-label={t('app.map.delete')}>
          <span>{deleteError ?? t('app.map.confirmDelete', { name: selected.name })}</span>
          <span className="row-actions">
            <button className="btn btn-map btn-danger-solid" disabled={deleting} onClick={removeSelected} autoFocus>
              {deleting ? t('app.map.deleting') : t('app.map.confirmYes')}
            </button>
            <button className="btn btn-map" disabled={deleting} onClick={() => setAskDelete(false)}>{t('app.map.confirmNo')}</button>
          </span>
        </div>
      ) : hint && <p className="map-hint">{hint}</p>}
      {fields.length > 0 && !draft && !editing && (
        <div className="field-chips">
          {fields.map((f) => (
            <button key={f.id} className={`chip ${String(f.id) === String(selectedId) ? 'is-sel' : ''}`} onClick={() => onSelect(f.id)}>
              {f.name} <small>{f.area_ha} ha</small>
            </button>
          ))}
        </div>
      )}
      {draft && (
        <FieldForm area={draft.area} crops={crops}
          onCancel={() => setDraft(null)}
          onSave={async (body) => { await onCreate({ ...body, polygon: draft.polygon }); setDraft(null) }} />
      )}
      {editing && selected && (
        <FieldForm key={editing.id} field={selected} area={editing.area} crops={crops} blocked={!editing.inside}
          onCancel={() => stopEdit(true)}
          onSave={async (body) => {
            const ll = polys.current[editing.id]?.getLatLngs()[0] ?? []
            const polygon = ll.map((p) => [+p.lat.toFixed(6), +p.lng.toFixed(6)])
            await onUpdate(editing.id, { ...body, ...(editing.changed ? { polygon } : {}) })
            stopEdit(false)
          }} />
      )}
    </section>
  )
}
