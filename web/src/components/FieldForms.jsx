import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef, useState } from 'react'
import { getCrops } from '../api.js'
import { useI18n } from '../i18n/index.jsx'
import { SCORE_KEYS } from './RotationCard.jsx'
import TermHelp from './TermHelp.jsx'

// Tap the field on an OpenStreetMap map (a circle marker: no image files to bundle)
export function FieldMap({ value, onChange }) {
  const { t } = useI18n()
  const box = useRef(null)
  const map = useRef(null)
  const dot = useRef(null)
  useEffect(() => {
    const m = L.map(box.current, { center: value ? [value.lat, value.lon] : [41.6, 21.75], zoom: value ? 13 : 8 })
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(m)
    m.on('click', (e) => onChange({ lat: +e.latlng.lat.toFixed(5), lon: +e.latlng.lng.toFixed(5) }))
    map.current = m
    return () => m.remove()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!map.current || !value) return
    const ll = [value.lat, value.lon]
    if (dot.current) dot.current.setLatLng(ll)
    else dot.current = L.circleMarker(ll, { radius: 9, color: '#000', weight: 3, fillColor: '#fff100', fillOpacity: 1 }).addTo(map.current)
  }, [value])
  const locate = () =>
    navigator.geolocation?.getCurrentPosition((p) => {
      const v = { lat: +p.coords.latitude.toFixed(5), lon: +p.coords.longitude.toFixed(5) }
      onChange(v)
      map.current?.setView([v.lat, v.lon], 14)
    })
  return (
    <div className="field-map">
      <div ref={box} className="map" role="application" aria-label={t('setup.mapLabel')} />
      <div className="map-foot">
        <span className="muted">{value ? `${value.lat}, ${value.lon}` : t('setup.tapMap')}</span>
        {'geolocation' in navigator && <button type="button" className="btn btn-ghost" onClick={locate}>{t('setup.myLocation')}</button>}
      </div>
    </div>
  )
}

// Crops by year; empty = "use what is common in my region"
export function RotationPicker({ value, onChange }) {
  const { t, lang } = useI18n()
  const [crops, setCrops] = useState([])
  useEffect(() => {
    getCrops().then((d) => setCrops(d.crops.filter((c) => !c.cover_crop))).catch(() => {})
  }, [])
  const years = [...value, '']
  const set = (i, crop) => {
    const next = [...value]
    if (crop) next[i] = crop
    else next.splice(i)
    onChange(next.slice(0, 4))
  }
  return (
    <div className="rot-picker">
      {years.slice(0, 4).map((c, i) => (
        <label key={i} className="select">
          <span>{t('rot.yearShort')}{i + 1}</span>
          <select value={c} onChange={(e) => set(i, e.target.value)}>
            <option value="">{i === 0 ? t('setup.notSure') : '—'}</option>
            {crops.map((x) => <option key={x.id} value={x.id}>{lang === 'mk' ? x.name_mk : x.name}</option>)}
          </select>
        </label>
      ))}
    </div>
  )
}

const LEVELS = [0, 0.5, 1, 2, 3]
export function PrioritySliders({ value, onChange }) {
  const { t } = useI18n()
  return (
    <div className="priorities">
      {SCORE_KEYS.map((k) => {
        const v = value[k] ?? 1
        const idx = Math.max(0, LEVELS.indexOf(LEVELS.reduce((a, b) => (Math.abs(b - v) < Math.abs(a - v) ? b : a))))
        return (
          <label key={k} className="slider">
            <span>{t(`rot.score_${k}`)} <TermHelp term={`score_${k}`} /> <strong>{t(`setup.level${idx}`)}</strong></span>
            <input type="range" min="0" max="4" step="1" value={idx}
              onChange={(e) => onChange({ ...value, [k]: LEVELS[Number(e.target.value)] })} />
          </label>
        )
      })}
    </div>
  )
}
