import L from 'leaflet'

// Base maps for every Niva map. Satellite is the default so farmers can see their field edges.
// Esri World Imagery is free to use with attribution; place names come from Esri's reference layer.
const SAT = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
const SAT_LABELS = 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}'
const OSM = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'

export function addBasemap(map, kind = 'satellite') {
  const group = L.layerGroup()
  if (kind === 'satellite') {
    L.tileLayer(SAT, { maxZoom: 19, maxNativeZoom: 18, attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics' }).addTo(group)
    L.tileLayer(SAT_LABELS, { maxZoom: 19, maxNativeZoom: 18, opacity: 0.9 }).addTo(group)
  } else {
    L.tileLayer(OSM, { maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' }).addTo(group)
  }
  group.addTo(map)
  group.eachLayer((l) => l.bringToBack())
  return group
}

// Area of a lat/lon polygon in hectares (spherical excess on a 6371 km Earth; fine for a field)
export function hectares(points) {
  if (!points || points.length < 3) return 0
  const R = 6371000
  const rad = (d) => (d * Math.PI) / 180
  let sum = 0
  for (let i = 0; i < points.length; i++) {
    const [la1, lo1] = points[i]
    const [la2, lo2] = points[(i + 1) % points.length]
    sum += rad(lo2 - lo1) * (2 + Math.sin(rad(la1)) + Math.sin(rad(la2)))
  }
  return Math.abs((sum * R * R) / 2) / 10000
}
