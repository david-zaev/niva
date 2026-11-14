// All calls to the Niva backend live here.
export const API_BASE = import.meta.env.VITE_API_BASE ?? 'https://niva-api.92-5-133-111.sslip.io'

async function get(path) {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`)
  return res.json()
}

export const getHealth = () => get('/health')
export const getLive = (fieldId) => get(`/fields/${fieldId}/live`)
export const getHistory = (fieldId, days = 7) => get(`/fields/${fieldId}/history?days=${days}`)
export const getField = (fieldId) => get(`/fields/${fieldId}`)
export const getClimate = (fieldId) => get(`/fields/${fieldId}/climate`)
export const getRotations = (fieldId, rain = 0, temp = 0) =>
  get(`/fields/${fieldId}/rotations?rain=${rain}&temp=${temp}`)
export const getForecast = (fieldId) => get(`/fields/${fieldId}/forecast`)
