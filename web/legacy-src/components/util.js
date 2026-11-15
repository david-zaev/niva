import { useEffect, useState } from 'react'
import { getCrops, peek } from '../api.js'
import { useI18n } from '../i18n/index.jsx'

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
