import { lazy, Suspense, useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { load, save, useI18n } from './i18n/index.jsx'
import MyField from './screens/MyField.jsx'
import Climate from './screens/Climate.jsx'
import Rotations from './screens/Rotations.jsx'
import RotationDetails from './screens/RotationDetails.jsx'
// the map (Leaflet) is only needed here: load these screens when opened
const More = lazy(() => import('./screens/More.jsx'))
const Setup = lazy(() => import('./screens/Setup.jsx'))
import Pair from './screens/Pair.jsx'
import { OfflineBanner, UpdateButton } from './components/StatusBars.jsx'
import './pwa.js'

const base = import.meta.env.BASE_URL

// Simple line icons, drawn with currentColor so they follow the theme
const icons = {
  field: 'M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21Zm0-9a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z',
  climate: 'M12 3v2m0 14v2M3 12h2m14 0h2M5.6 5.6 7 7m10 10 1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z',
  rotations: 'M4 12a8 8 0 0 1 14-5.3M20 12a8 8 0 0 1-14 5.3M18 3v4h-4M6 21v-4h4',
  more: 'M4 6h16M4 12h16M4 18h16',
}

const tabs = [
  { key: 'field', path: '/' },
  { key: 'climate', path: '/climate' },
  { key: 'rotations', path: '/rotations' },
  { key: 'more', path: '/more' },
]

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

export default function App() {
  const { t } = useI18n()
  const [theme, setTheme] = useTheme()

  return (
    <div className="app">
      <header className="topbar">
        <img src={`${base}icons/logo.svg`} alt="" width="34" height="34" />
        <span className="wordmark">Niva</span>
        <span className="pill">{t('badge')}</span>
        <UpdateButton />
      </header>
      <OfflineBanner />

      <nav className="tabs" aria-label="Niva">
        {tabs.map(({ key, path }) => (
          <NavLink key={key} to={path} end={path === '/'} className="tab">
            <span className="tab-icon">
              <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
                <path d={icons[key]} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <span>{t(`tabs.${key}`)}</span>
          </NavLink>
        ))}
      </nav>

      <main className="content">
        <Suspense fallback={<p className="card muted">{t('field.loading')}</p>}>
        <Routes>
          <Route path="/" element={<MyField />} />
          <Route path="/climate" element={<Climate />} />
          <Route path="/rotations" element={<Rotations />} />
          <Route path="/rotations/:id" element={<RotationDetails />} />
          <Route path="/setup" element={<Setup />} />
          <Route path="/pair" element={<Pair />} />
          <Route path="/more" element={<More theme={theme} setTheme={setTheme} />} />
          <Route path="*" element={<MyField />} />
        </Routes>
        </Suspense>
      </main>
    </div>
  )
}
