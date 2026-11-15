import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import Logo from './components/Logo.jsx'
import LanguagePicker from './components/LanguagePicker.jsx'
import Auth, { currentSession, logOut } from './screens/Auth.jsx'
import { useI18n } from './i18n/index.jsx'
import HealthCard from './components/HealthCard.jsx'
import FarmMap from './components/FarmMap.jsx'
import Rotations from './components/Rotations.jsx'
import { Evidence, FarmPlan } from './components/Evidence.jsx'

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
  const { t } = useI18n()
  const [session, setSession] = useState(currentSession)
  const [farm, setFarm] = useState(null)
  const [crops, setCrops] = useState([])
  const [selected, setSelected] = useState(null)
  const [rot, setRot] = useState(null)
  const [profile, setProfile] = useState(null)
  const [plan, setPlan] = useState(null)
  const [err, setErr] = useState(null)

  const loadFarm = useCallback(async (keep) => {
    const { farm_id } = await api.demo()
    const f = await api.farm(farm_id)
    setFarm(f)
    setSelected((cur) => keep ?? cur ?? f.fields[0]?.id ?? null)
    api.plan(farm_id).then(setPlan).catch(() => {})
    return f
  }, [])

  useEffect(() => {
    loadFarm().catch((e) => setErr(`Cannot reach the Niva API (${e.message}). Check that the server is running.`))
    api.crops().then((d) => setCrops(d.crops)).catch(() => {})
  }, [loadFarm])

  useEffect(() => {
    if (!selected) return undefined
    let alive = true
    setRot(null); setProfile(null)
    api.rotations(selected).then((d) => alive && setRot(d)).catch((e) => alive && setErr(e.message))
    const loadProfile = () => api.profile(selected).then((d) => {
      if (!alive) return
      setProfile(d)
      if (d.ndvi_status === 'loading') setTimeout(loadProfile, 15000)
    }).catch(() => {})
    loadProfile()
    return () => { alive = false }
  }, [selected])

  const field = farm?.fields.find((f) => f.id === selected)

  const choose = async (rotationId) => {
    await api.updateField(selected, { chosen_rotation: rotationId })
    setRot((r) => ({ ...r, chosen: rotationId }))
    api.plan(farm.id).then(setPlan).catch(() => {})
  }

  const create = async (body) => {
    const f = await api.createField(farm.id, body)
    await loadFarm(f.id)
    setSelected(f.id)
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
        {farm && field && (
          <div className="page">
            <HealthCard fieldId={selected} fieldName={field.name} />
            <FarmMap fields={farm.fields} selectedId={selected} onSelect={setSelected} onCreate={create} crops={crops} />
            <Rotations data={rot} onChoose={choose} />
            <Evidence profile={profile} />
            <FarmPlan plan={plan} />
            <footer className="foot muted small">
              Niva supports farmer judgement; it does not replace it. Check every plan with a local agronomist.
              Data: NASA POWER, NASA SMAP, NASA MODIS (LP DAAC), NASA NASADEM/SRTM, ISRIC SoilGrids, ZPIS and MakStat.
            </footer>
          </div>
        )}
      </main>
    </div>
  )
}
