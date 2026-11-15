import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useRef } from 'react'
import { useI18n } from '../i18n/index.jsx'
import { addBasemap } from './basemap.js'

const MACEDONIA = [41.6, 21.7]

// A plain satellite map with place names, centred on the field. Nothing drawn on top.
export default function FieldMap({ lat, lon }) {
  const { t } = useI18n()
  const box = useRef(null)
  const map = useRef(null)

  useEffect(() => {
    const m = L.map(box.current, { zoomControl: true, attributionControl: true, scrollWheelZoom: false })
    addBasemap(m, 'satellite')
    m.setView(MACEDONIA, 8)
    map.current = m
    return () => { m.remove(); map.current = null }
  }, [])

  useEffect(() => {
    if (map.current && lat != null && lon != null) map.current.setView([lat, lon], 13)
  }, [lat, lon])

  return (
    <article className="card field-map-card">
      <h2>{t('map.title')}</h2>
      <div ref={box} className="field-map-view" role="application" aria-label={t('map.title')} />
    </article>
  )
}
