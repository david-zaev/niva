import L from 'leaflet'

// Base maps for every Niva map. Satellite is the default so farmers can see their field edges.
// Esri World Imagery is free to use with attribution; place names come from Esri's label-only canvas layer.
const SAT = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
// place names only (Esri's dark-grey canvas labels): none of the glowing municipal boundary lines over the photo
const SAT_LABELS = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}'
const OSM = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'

export function addBasemap(map, kind = 'satellite') {
  const group = L.layerGroup()
  if (kind === 'satellite') {
    // place names get their own pane above the photo (tiles sit at z 200) and below field shapes and pins
    if (!map.getPane('labels')) {
      const pane = map.createPane('labels')
      pane.style.zIndex = 350
      pane.style.pointerEvents = 'none'
      // the grey canvas labels are made white and given a soft shadow so they read on the photo
      pane.style.filter = 'brightness(1.9) drop-shadow(0 0 1.5px rgb(0 0 0 / 0.9))'
    }
    L.tileLayer(SAT, { maxZoom: 19, maxNativeZoom: 18, attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics' }).addTo(group)
    L.tileLayer(SAT_LABELS, { maxZoom: 19, maxNativeZoom: 16, pane: 'labels' }).addTo(group)
  } else {
    L.tileLayer(OSM, { maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' }).addTo(group)
  }
  group.addTo(map)
  group.eachLayer((l) => l.bringToBack())
  return group
}
