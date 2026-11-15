import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import Logo from './components/Logo.jsx'
import LanguagePicker from './components/LanguagePicker.jsx'
import Auth, { currentSession, logOut } from './screens/Auth.jsx'
import { useI18n } from './i18n/index.jsx'
import HealthCard from './components/HealthCard.jsx'
import FarmMap from './components/FarmMap.jsx'
import Rotations from './components/Rotations.jsx'

// The visitor's own farm ({ id, key }), kept in this browser for each account. Everyone sees the shared demo
// farm; fields a visitor draws go to their own farm, which only this browser can change.
const ownKey = (session) => `niva.farm.${session?.email ?? 'guest'}`
function readOwn(session) {
  try { return JSON.parse(localStorage.getItem(ownKey(session))) } catch { return null }
}
function writeOwn(session, own) {
  try {
    if (own) localStorage.setItem(ownKey(session), JSON.stringify(own))
    else localStorage.removeItem(ownKey(session))
  } catch { /* private mode: the fields last until the tab closes */ }
}

// Follow the phone's light/dark setting (the brand theme switches on data-theme)
function useTheme() {
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const apply = () => { document.documentElement.dataset.theme = media.matches ? 'dark' : 'light' }
    apply()
    media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [])
}

export default function App() {
  useTheme()
  const { t, lang } = useI18n()
  const [session, setSession] = useState(currentSession)
  const [farm, setFarm] = useState(null)
  const [crops, setCrops] = useState([])
  const [selected, setSelected] = useState(null)
  const [rot, setRot] = useState(null)
  const [err, setErr] = useState(null)
  const [version, setVersion] = useState(0) // bumped after an edit, so the advice is fetched again

  const own = useRef(null) // { id, key } of this visitor's farm, once they have drawn a field

  // the demo farm's fields (locked) and the visitor's own fields, shown together
  const loadFarm = useCallback(async (keep) => {
    const { farm_id } = await api.demo()
    const mine = own.current
    const [demo, ownFarm] = await Promise.all([
      api.farm(farm_id),
      mine ? api.farm(mine.id).catch((e) => { if (e.status === 404) { own.current = null; writeOwn(session, null) } return null }) : null,
    ])
    const f = { ...demo, fields: [...demo.fields.map((x) => ({ ...x, demo: true })), ...(ownFarm?.fields ?? [])] }
    setFarm(f)
    setSelected((cur) => keep ?? cur ?? f.fields[0]?.id ?? null)
    return f
  }, [session])

  useEffect(() => {
    if (!session) return
    own.current = readOwn(session)
    loadFarm().catch((e) => setErr(t('app.apiDown', { msg: e.message })))
    api.crops().then((d) => setCrops(d.crops)).catch(() => {})
  }, [loadFarm, session])

  useEffect(() => {
    setRot(null)
    if (!selected) return undefined
    let alive = true
    api.rotations(selected, lang).then((d) => alive && setRot(d)).catch((e) => alive && setErr(e.message))
    return () => { alive = false }
  }, [selected, lang, version])

  const field = farm?.fields.find((f) => f.id === selected)

  const create = async (body) => {
    if (!own.current) {
      const made = await api.createFarm(session?.name ? `${session.name}` : 'My fields')
      own.current = { id: made.id, key: made.key }
      writeOwn(session, own.current)
    }
    const f = await api.createField(own.current.id, own.current.key, body)
    await loadFarm(f.id)
    setSelected(f.id)
  }

  const update = async (id, body) => {
    await api.updateField(id, own.current?.key, body)
    await loadFarm(id)
    setVersion((v) => v + 1)
  }

  const remove = async (id) => {
    await api.deleteField(id, own.current?.key)
    setSelected(null)
    await loadFarm()
  }

  if (!session) return <Auth onEnter={setSession} />

  return (
    <div className="app">
      <header className="topbar">
        <a href="./" className="brand" aria-label="Niva"><Logo /></a>
        <div className="top-right">
          <span className="farm-name">{farm?.name ?? ''}</span>
          <LanguagePicker />
          <button type="button" className="logout" onClick={() => { logOut(); setSession(null) }}>{t('auth.logout')}</button>
        </div>
      </header>
      <main className="content">
        {err && <p className="card error">{err}</p>}
        {farm && (
          <div className="page">
            {field
              ? <HealthCard fieldId={selected} fieldName={field.name} />
              : <section className="card health health-none">
                  <p className="eyebrow">{t('app.emptyEyebrow')}</p>
                  <h2 className="health-label">{t('app.emptyTitle')}</h2>
                  <p className="health-summary">{t('app.emptyText')}</p>
                </section>}
            <FarmMap fields={farm.fields} selectedId={selected} onSelect={setSelected} onCreate={create} onUpdate={update} onDelete={remove} crops={crops} />
            {field && <>
              <Rotations data={rot} />
            </>}
            <footer className="foot muted small">
              {t('app.footer')} {t('app.footerData')}
            </footer>
          </div>
        )}
      </main>
    </div>
  )
}
