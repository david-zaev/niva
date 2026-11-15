import L from 'leaflet'

// Base maps for every Niva map. Satellite is the default so farmers can see their field edges.
// Esri World Imagery is free to use with attribution; place names come from Esri's reference layer.
const SAT = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
const SAT_LABELS = 'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}'
const OSM = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'

export function addBasemap(map, kind = 'satellite') {
  const group = L.layerGroup()
  if (kind === 'satellite') {
    // place names get their own pane above the photo (tiles sit at z 200) and below field shapes and pins
    if (!map.getPane('labels')) {
      const pane = map.createPane('labels')
      pane.style.zIndex = 350
      pane.style.pointerEvents = 'none'
    }
    L.tileLayer(SAT, { maxZoom: 19, maxNativeZoom: 18, attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics' }).addTo(group)
    L.tileLayer(SAT_LABELS, { maxZoom: 19, maxNativeZoom: 18, pane: 'labels' }).addTo(group)
  } else {
    L.tileLayer(OSM, { maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' }).addTo(group)
  }
  group.addTo(map)
  group.eachLayer((l) => l.bringToBack())
  return group
}
