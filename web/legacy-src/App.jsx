import { Suspense, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fieldId, getField, onFieldChange } from './api.js'
import { load, save, useI18n } from './i18n/index.jsx'
import MyField from './screens/MyField.jsx'
import Auth, { currentSession, logOut } from './screens/Auth.jsx'
import FieldSwitcher from './components/FieldSwitcher.jsx'
import { OfflineBanner, UpdateButton } from './components/StatusBars.jsx'
import Logo from './components/Logo.jsx'
import LanguagePicker from './components/LanguagePicker.jsx'
import './pwa.js'

// "auto" follows the phone; the brand theme switches on data-theme="dark"
function useTheme() {
  const [theme, setThemeState] = useState(() => load('niva.theme', 'auto'))
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const apply = () => {
      const dark = theme === 'dark' || (theme === 'auto' && media.matches)
      document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    }
    apply()
    media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [theme])
  const setTheme = (next) => {
    setThemeState(next)
    save('niva.theme', next)
  }
  return [theme, setTheme]
}

// After the first screen shows, quietly fetch the page's data so switching field is instant
function usePreload(current) {
  useEffect(() => {
    const idle = window.requestIdleCallback ?? ((fn) => setTimeout(fn, 1200))
    const id = fieldId()
    idle(() => { // at the latest after 2 s, even if the phone never goes idle
      Promise.allSettled([getField(id)])
    }, { timeout: 2000 })
  }, [current])
}

export default function App() {
  const { t } = useI18n()
  useTheme()
  const [session, setSession] = useState(currentSession)
  const [current, setCurrent] = useState(fieldId)
  useEffect(() => onFieldChange(setCurrent), [])
  useEffect(() => {
    window.scrollTo({ top: 0 })
  }, [current])
  usePreload(current)

  if (!session) return <Auth onEnter={setSession} />

  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand" aria-label="Niva"><Logo /></Link>
        <div className="top-right">
          <FieldSwitcher current={current} />
          <UpdateButton />
          <LanguagePicker />
          <button type="button" className="logout" onClick={() => { logOut(); setSession(null) }}>{t('auth.logout')}</button>
        </div>
      </header>

      <OfflineBanner />

      <main className="content">
        <div className="page" key={current}>
        <Suspense fallback={<p className="muted">{t('field.loading')}</p>}>
          <MyField />
        </Suspense>
        </div>
      </main>
    </div>
  )
}
