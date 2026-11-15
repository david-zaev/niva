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

export const api = {
  demo: () => call('/demo'),
  farm: (id) => call(`/farms/${id}`),
  plan: (id) => call(`/farms/${id}/plan`),
  crops: () => call('/crops'),
  createField: (farmId, body) => call(`/farms/${farmId}/fields`, { method: 'POST', body }),
  updateField: (id, body) => call(`/fields/${id}`, { method: 'PATCH', body }),
  deleteField: (id) => call(`/fields/${id}`, { method: 'DELETE' }),
  rotations: (id) => call(`/fields/${id}/rotations`),
  profile: (id) => call(`/fields/${id}/profile`),
  live: (id, minutes = 120) => call(`/fields/${id}/live?minutes=${minutes}`),
}

export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
