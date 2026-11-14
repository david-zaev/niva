// All calls to the Niva backend live here.
import { load, save } from './i18n/index.jsx'

export const API_BASE = import.meta.env.VITE_API_BASE ?? 'https://niva-api.92-5-133-111.sslip.io'

// ---- freshness, for the OfflineBanner ----
// The service worker answers from its cache when the network is gone (NetworkFirst). The server's Date header
// (exposed by CORS) then tells how old the shown data is.
const listeners = new Set()
export const net = { dataTime: null, failed: false, cached: false }
function report(dataTime, failed) {
  if (dataTime) {
    net.dataTime = dataTime
    net.cached = Date.now() - dataTime > 60000 // an old Date header = the service worker's saved copy
  }
  net.failed = failed
  listeners.forEach((fn) => fn({ ...net }))
}
export function onNet(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

async function call(method, path, body, headers = {}) {
  let res
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json', ...headers } : headers,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch (e) {
    report(null, true)
    throw e
  }
  const date = Date.parse(res.headers.get('date') ?? '')
  report(Number.isNaN(date) ? null : date, false)
  if (!res.ok) {
    const err = new Error(`${path}: HTTP ${res.status}`)
    err.status = res.status
    throw err
  }
  return res.json()
}
// Last answer per path, kept in memory: a tab you come back to shows its data at once and refreshes quietly.
// Requests already on their way are shared (the background preload and a screen can ask at the same time).
const cache = new Map()
const inflight = new Map()
function get(path) {
  if (inflight.has(path)) return inflight.get(path)
  const p = call('GET', path)
    .then((data) => {
      cache.set(path, data)
      return data
    })
    .finally(() => inflight.delete(path))
  inflight.set(path, p)
  return p
}
export const peek = (path) => cache.get(path) ?? null

export const paths = {
  live: (id) => `/fields/${id}/live`,
  field: (id) => `/fields/${id}`,
  climate: (id) => `/fields/${id}/climate`,
  forecast: (id) => `/fields/${id}/forecast`,
  terrain: (id) => `/fields/${id}/terrain`,
  smap: (id) => `/fields/${id}/smap?days=365`,
  rotations: (id, rain = 0, temp = 0) => `/fields/${id}/rotations?rain=${rain}&temp=${temp}`,
}
export const getHealth = () => get('/health')
export const getLive = (fieldId) => get(paths.live(fieldId))
export const getHistory = (fieldId, days = 7) => get(`/fields/${fieldId}/history?days=${days}`)
export const getField = (fieldId) => get(paths.field(fieldId))
export const getClimate = (fieldId) => get(paths.climate(fieldId))
export const getRotations = (fieldId, rain = 0, temp = 0) => get(paths.rotations(fieldId, rain, temp))
export const getForecast = (fieldId) => get(paths.forecast(fieldId))
export const getTerrain = (fieldId) => get(paths.terrain(fieldId))
export const getSmap = (fieldId) => get(paths.smap(fieldId))
export const getCrops = () => get('/crops')
export const getPrices = () => get('/prices')
export const getBuyers = (crop) => get(`/buyers${crop ? `?crop=${encodeURIComponent(crop)}` : ''}`)

// ---- the field this phone shows, and the owner token if this phone created it ----
export const DEMO_FIELD = '1'
export const fieldId = () => load('niva.fieldId', DEMO_FIELD)
function tokens() {
  try {
    return JSON.parse(load('niva.owner', '{}')) || {}
  } catch {
    return {}
  }
}
export const ownerToken = (id = fieldId()) => tokens()[id] ?? null
export function selectField(id, token) {
  save('niva.fieldId', String(id))
  if (token) save('niva.owner', JSON.stringify({ ...tokens(), [id]: token }))
  fieldListeners.forEach((fn) => fn(String(id))) // the whole app switches to this field
}

export async function createField(body) {
  const f = await call('POST', '/fields', body)
  selectField(f.id, f.owner_token)
  return f
}
export const patchField = (id, body) =>
  call('PATCH', `/fields/${id}`, body, { 'X-Owner-Token': ownerToken(id) ?? '' }).finally(() => forget(id))
export const pairDevice = (id, deviceId, pairCode) =>
  call('POST', '/devices/pair', { device_id: deviceId, pair_code: pairCode, field_id: Number(id) },
    { 'X-Owner-Token': ownerToken(id) ?? '' })

// ---- several fields per phone: every field this phone created, plus the demo ----
export const myFieldIds = () => [...new Set([DEMO_FIELD, ...Object.keys(tokens())])]
export const isOwner = (id = fieldId()) => ownerToken(id) != null
const fieldListeners = new Set()
export function onFieldChange(fn) {
  fieldListeners.add(fn)
  return () => fieldListeners.delete(fn)
}
export const switchField = (id) => selectField(id)
// after a change, forget saved answers about that field so every screen asks again
export function forget(id) {
  for (const key of [...cache.keys()]) if (key.startsWith(`/fields/${id}`) || key.startsWith('/fields?')) cache.delete(key)
}

Object.assign(paths, {
  fields: (ids) => `/fields?ids=${ids.join(',')}`,
  summary: (id) => `/fields/${id}/summary`,
  metrics: (id) => `/fields/${id}/metrics`,
  soil: (id) => `/fields/${id}/soil`,
  ndvi: (id) => `/fields/${id}/ndvi`,
  pests: (id) => `/fields/${id}/pests`,
  market: (id) => `/fields/${id}/market`,
  plantings: (id) => `/fields/${id}/plantings`,
  harvests: (id) => `/fields/${id}/harvests`,
  weather: (id) => `/fields/${id}/weather`,
})
export const getFields = (ids = myFieldIds()) => get(paths.fields(ids))
export const getSummary = (id) => get(paths.summary(id))
export const getMetrics = (id) => get(paths.metrics(id))
export const getSoil = (id) => get(paths.soil(id))
export const getNdvi = (id) => get(paths.ndvi(id))
export const getPests = (id) => get(paths.pests(id))
export const getMarket = (id) => get(paths.market(id))
export const getPlantings = (id) => get(paths.plantings(id))
export const getHarvests = (id) => get(paths.harvests(id))
export const getWeather = (id) => get(paths.weather(id))

const owned = (method, id, path, body) =>
  call(method, `/fields/${id}${path}`, body, { 'X-Owner-Token': ownerToken(id) ?? '' }).finally(() => forget(id))
export const addPlanting = (id, body) => owned('POST', id, '/plantings', body)
export const deletePlanting = (id, pid) => owned('DELETE', id, `/plantings/${pid}`)
export const addHarvest = (id, body) => owned('POST', id, '/harvests', body)
export const deleteHarvest = (id, hid) => owned('DELETE', id, `/harvests/${hid}`)
export const addPestReport = (id, body) => owned('POST', id, '/pest-reports', body)
export const deletePestReport = (id, rid) => owned('DELETE', id, `/pest-reports/${rid}`)
export const saveOutline = (id, polygon) => owned('PATCH', id, '', { polygon })
