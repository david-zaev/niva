import { useEffect, useState } from 'react'
import { getCrops, peek } from '../api.js'
import { useI18n } from '../i18n/index.jsx'

// "{n} mm" + {n: 4} -> "4 mm"
export const fmt = (s, vars = {}) => Object.entries(vars).reduce((out, [k, v]) => out.replaceAll(`{${k}}`, v), s)

export function useDay() {
  const { lang } = useI18n()
  const loc = lang === 'mk' ? 'mk-MK' : 'en-GB'
  return (iso, opts = { weekday: 'short', day: 'numeric', month: 'short' }) =>
    iso ? new Intl.DateTimeFormat(loc, opts).format(new Date(`${iso.slice(0, 10)}T12:00:00`)) : '—'
}

// crop id -> {name, name_mk, ...}; cropName(id) in the app language
export function useCrops() {
  const { lang } = useI18n()
  const [list, setList] = useState(() => peek('/crops')?.crops ?? [])
  useEffect(() => {
    getCrops().then((d) => setList(d.crops ?? [])).catch(() => {})
  }, [])
  const byId = Object.fromEntries(list.map((c) => [c.id, c]))
  const cropName = (id) => (byId[id] ? (lang === 'mk' ? byId[id].name_mk : byId[id].name) : id)
  return { list, byId, cropName }
}

// Load one API answer for the current field; shows the saved copy at once and refreshes it
export function useData(getter, path, deps = []) {
  const [data, setData] = useState(() => (path ? peek(path) : null))
  const [error, setError] = useState(null)
  const [tick, setTick] = useState(0)
  useEffect(() => {
    let alive = true
    getter().then((d) => alive && (setData(d), setError(null))).catch((e) => alive && setError(e))
    return () => { alive = false }
  }, [...deps, tick]) // eslint-disable-line react-hooks/exhaustive-deps
  return { data, error, reload: () => setTick((n) => n + 1) }
}

export const today = () => new Date().toISOString().slice(0, 10)
