// All calls to the Niva backend.
export const API_BASE = import.meta.env.VITE_API_BASE ?? 'https://niva-api.92-5-133-111.sslip.io'

async function call(path, opts = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(opts.headers ?? {}) },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try { msg = (await res.json()).detail ?? msg } catch { /* not json */ }
    const err = new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    err.status = res.status
    throw err
  }
  return res.status === 204 ? null : res.json()
}

const owner = (key) => ({ 'X-Farm-Key': key })

export const api = {
  demo: () => call('/demo'),
  farm: (id) => call(`/farms/${id}`),
  createFarm: (name) => call('/farms', { method: 'POST', body: { name } }),
  plan: (id) => call(`/farms/${id}/plan`),
  crops: () => call('/crops'),
  // the visitor's own fields: only their farm's key may change them (the demo farm is shared and locked)
  createField: (farmId, key, body) => call(`/farms/${farmId}/fields`, { method: 'POST', body, headers: owner(key) }),
  updateField: (id, key, body) => call(`/fields/${id}`, { method: 'PATCH', body, headers: owner(key) }),
  deleteField: (id, key) => call(`/fields/${id}`, { method: 'DELETE', headers: owner(key) }),
  rotations: (id, lang = 'en') => call(`/fields/${id}/rotations?lang=${lang}`),
  profile: (id) => call(`/fields/${id}/profile`),
  live: (id, minutes = 120, lang = 'en', signal) => call(`/fields/${id}/live?minutes=${minutes}&lang=${lang}`, { signal, cache: 'no-store' }),
}

export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
