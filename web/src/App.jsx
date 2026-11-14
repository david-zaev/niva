import { lazy, Suspense, useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Link, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { fieldId, getClimate, getField, getForecast, getRotations } from './api.js'
import { load, save, useI18n } from './i18n/index.jsx'
import MyField from './screens/MyField.jsx'
import Climate from './screens/Climate.jsx'
import Rotations from './screens/Rotations.jsx'
import RotationDetails from './screens/RotationDetails.jsx'
// the map (Leaflet) is only needed here: load these screens when opened
const loadMore = () => import('./screens/More.jsx')
const loadSetup = () => import('./screens/Setup.jsx')
const More = lazy(loadMore)
const Setup = lazy(loadSetup)
import Pair from './screens/Pair.jsx'
import { OfflineBanner, UpdateButton } from './components/StatusBars.jsx'
import FarmGrid from './components/FarmGrid.jsx'
import Logo from './components/Logo.jsx'
import LanguagePicker from './components/LanguagePicker.jsx'
import './pwa.js'

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

// After the first screen shows, quietly fetch the other tabs and their code, so switching is instant
function usePreload() {
  useEffect(() => {
    const idle = window.requestIdleCallback ?? ((fn) => setTimeout(fn, 1200))
    const id = fieldId()
    idle(() => { // at the latest after 2 s, even if the phone never goes idle
      Promise.allSettled([getField(id), getForecast(id), getClimate(id), getRotations(id), loadMore(), loadSetup()])
    }, { timeout: 2000 })
  }, [])
}

const activeIndex = (pathname) => {
  if (pathname === '/') return 0
  const i = tabs.findIndex((tab) => tab.path !== '/' && pathname.startsWith(tab.path))
  return i
}

// Attached bottom navigation on phones, left sidebar on a PC.
function TabBar({ t }) {
  const { pathname } = useLocation()
  const nav = useRef(null)
  const [pill, setPill] = useState(null)
  const index = activeIndex(pathname)
  const measure = useCallback(() => {
    const el = nav.current?.querySelectorAll('.tab')[index]
    setPill(el ? { x: el.offsetLeft, y: el.offsetTop, w: el.offsetWidth, h: el.offsetHeight } : null)
  }, [index])
  useLayoutEffect(measure, [measure, t])
  useEffect(() => {
    const ro = new ResizeObserver(measure)
    if (nav.current) ro.observe(nav.current)
    document.fonts?.ready.then(measure)
    return () => ro.disconnect()
  }, [measure])
  return (
    <nav className="tabs" aria-label="Niva" ref={nav}>
      <span className={`tab-pill ${pill ? '' : 'is-hidden'}`} aria-hidden="true"
        style={pill ? { transform: `translate(${pill.x}px, ${pill.y}px)`, width: pill.w, height: pill.h } : undefined} />
      {tabs.map(({ key, path }, i) => (
        <NavLink key={key} to={path} end={path === '/'} className={`tab ${i === index ? 'is-on' : ''}`}>
          <svg className="tab-icon" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            <path d={icons[key]} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="tab-label">{t(`tabs.${key}`)}</span>
        </NavLink>
      ))}
    </nav>
  )
}

export default function App() {
  const { t } = useI18n()
  const [theme, setTheme] = useTheme()
  const { pathname } = useLocation()
  // a new page fades in; moving within Rotations (sliders, details) keeps its place
  const pageKey = pathname.startsWith('/rotations') ? '/rotations' : pathname
  useEffect(() => {
    window.scrollTo({ top: 0 })
  }, [pageKey])
  usePreload()

  return (
    <div className="app">
      <FarmGrid />
      <header className="topbar">
        <Link to="/" className="brand" aria-label="Niva"><Logo /></Link>
        <div className="top-right">
          <UpdateButton />
          <LanguagePicker />
        </div>
      </header>

      <TabBar t={t} />
      <OfflineBanner />

      <main className="content">
        <div className="page" key={pageKey}>
        <Suspense fallback={<p className="muted">{t('field.loading')}</p>}>
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
        </div>
      </main>
    </div>
  )
}
