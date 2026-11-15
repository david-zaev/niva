// Which kind of soil the field has (picked on this phone, or saved on the server), and what a probe reading means for it.
import { load } from './i18n/index.jsx'

// Five soils in the words farmers use. fc / wp / sat = field capacity, wilting point and saturation in % of
// volume: the middle of the FAO-56 Table 19 range for the matching texture. Approximate, check with an agronomist.
const SOILS = [
  { id: 'alluvial', fao: 'Fluvisols', texture: 'silt loam', fc: 29, wp: 15, sat: 48 },
  { id: 'smolnica', fao: 'Vertisols', texture: 'clay', fc: 36, wp: 22, sat: 50 },
  { id: 'loam', fao: 'Cambisols / Luvisols', texture: 'loam', fc: 25, wp: 12, sat: 46 },
  { id: 'red', fao: 'Chromic Luvisols', texture: 'clay loam', fc: 33, wp: 20, sat: 48 },
  { id: 'sandy', fao: 'Arenosols / Regosols', texture: 'sand', fc: 12, wp: 5, sat: 40 },
]
const soilById = (id) => SOILS.find((s) => s.id === id) ?? null

// The soil picked on this phone wins over the server's copy
export function fieldSoil(id, field) {
  let local = {}
  try { local = JSON.parse(load('niva.fieldMeta', '{}'))?.[id] ?? {} } catch { /* nothing saved */ }
  return local.soil ?? field?.soil_type ?? null
}

// ---- the capacitive probe ----
// The firmware sends 0 % in dry air and 100 % in water. Soil is full of water at its saturation point, so the
// water share of the soil volume is roughly reading x saturation. What the plant can use sits between wilting
// point and field capacity, which is why 40 % is fine in sand and too dry in heavy clay.
export function soilWater(pct, soilId) {
  const s = soilById(soilId)
  if (pct == null) return null
  if (!s) return { level: pct < 25 ? 'dry' : pct > 70 ? 'wet' : 'good', vwc: null, available: null, refill_mm: null, soil: null }
  const vwc = (pct / 100) * s.sat
  const available = (vwc - s.wp) / (s.fc - s.wp) // 0 = wilting, 1 = field capacity
  const level = available < 0.4 ? 'dry' : available > 1.25 ? 'wet' : 'good'
  // litres per m2 (= mm) to bring the top 30 cm back to field capacity
  const refill_mm = vwc < s.fc ? Math.round(((s.fc - vwc) / 100) * 300) : 0
  return { level, vwc, available, refill_mm, soil: s }
}
