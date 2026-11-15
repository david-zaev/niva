// All calls to the Niva backend live here.
import { load, save } from './i18n/index.jsx'

const API_BASE = import.meta.env.VITE_API_BASE ?? 'https://niva-api.92-5-133-111.sslip.io'

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

async function call(path) {
  let res
  try {
    res = await fetch(`${API_BASE}${path}`)
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
// Last answer per path, kept in memory, so a field you come back to shows its data at once and refreshes quietly.
// Requests already on their way are shared (the background preload and a screen can ask at the same time).
const cache = new Map()
const inflight = new Map()
function get(path) {
  if (inflight.has(path)) return inflight.get(path)
  const p = call(path)
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
  fields: (ids) => `/fields?ids=${ids.join(',')}`,
}
export const getLive = (fieldId) => get(paths.live(fieldId))
export const getField = (fieldId) => get(paths.field(fieldId))
export const getFields = (ids = myFieldIds()) => get(paths.fields(ids))
export const getCrops = () => get('/crops')

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
export const isOwner = (id = fieldId()) => tokens()[id] != null

const fieldListeners = new Set()
export function onFieldChange(fn) {
  fieldListeners.add(fn)
  return () => fieldListeners.delete(fn)
}
export function switchField(id) {
  save('niva.fieldId', String(id))
  fieldListeners.forEach((fn) => fn(String(id))) // the whole app switches to this field
}

// ---- several fields per phone: every field this phone created, plus the demo ----
function demoIds() {
  try {
    return JSON.parse(load('niva.demoIds', '[]')).map(String)
  } catch {
    return []
  }
}
export const myFieldIds = () => [...new Set([DEMO_FIELD, ...demoIds(), ...Object.keys(tokens())])]
// "Try the demo farm": the read-only demo fields join this phone's list, no form to fill in.
// An older server without /demo-fields still opens the one demo field.
export async function openDemoFarm() {
  let ids = [DEMO_FIELD]
  try {
    const d = await get('/demo-fields')
    if (d.fields?.length) ids = d.fields.map((f) => String(f.id))
  } catch { /* keep the single demo field */ }
  save('niva.demoIds', JSON.stringify(ids))
  switchField(ids[0])
  return ids
}
