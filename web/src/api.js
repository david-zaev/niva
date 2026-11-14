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
const get = (path) => call('GET', path)

export const getHealth = () => get('/health')
export const getLive = (fieldId) => get(`/fields/${fieldId}/live`)
export const getHistory = (fieldId, days = 7) => get(`/fields/${fieldId}/history?days=${days}`)
export const getField = (fieldId) => get(`/fields/${fieldId}`)
export const getClimate = (fieldId) => get(`/fields/${fieldId}/climate`)
export const getRotations = (fieldId, rain = 0, temp = 0) =>
  get(`/fields/${fieldId}/rotations?rain=${rain}&temp=${temp}`)
export const getForecast = (fieldId) => get(`/fields/${fieldId}/forecast`)
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
}

export async function createField(body) {
  const f = await call('POST', '/fields', body)
  selectField(f.id, f.owner_token)
  return f
}
export const patchField = (id, body) => call('PATCH', `/fields/${id}`, body, { 'X-Owner-Token': ownerToken(id) ?? '' })
export const pairDevice = (id, deviceId, pairCode) =>
  call('POST', '/devices/pair', { device_id: deviceId, pair_code: pairCode, field_id: Number(id) },
    { 'X-Owner-Token': ownerToken(id) ?? '' })
