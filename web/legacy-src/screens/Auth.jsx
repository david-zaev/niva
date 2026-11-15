import { useEffect, useState } from 'react'
import { DEMO_FIELD, getLive } from '../api.js'
import Logo from '../components/Logo.jsx'
import LanguagePicker from '../components/LanguagePicker.jsx'
import { useI18n } from '../i18n/index.jsx'

// Link for the "watch the live demo" button. Leave empty to open the app's live demo field instead.
export const DEMO_URL = ''

// Accounts live on this device for now (there are no server accounts yet). Passwords are kept only as a
// salted SHA-256 hash, never as text.
const ACCOUNTS = 'niva.accounts'
const SESSION = 'niva.session'

function read(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback } catch { return fallback }
}
function write(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* private mode: not remembered */ }
}

async function hash(password, salt) {
  const data = new TextEncoder().encode(`${salt}:${password}`)
  const digest = await crypto.subtle.digest('SHA-256', data)
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

// True while the demo field's sensor (the ESP32) is sending: its last reading is under 30 s old.
// The ESP32 sends every 5 s, so this checks at the same pace.
function useSensorLive() {
  const [live, setLive] = useState(false)
  useEffect(() => {
    let alive = true
    const tick = () => getLive(DEMO_FIELD)
      .then((d) => {
        const time = d?.reading?.time
        if (alive) setLive(time != null && Date.now() - new Date(time).getTime() < 30000)
      })
      .catch(() => alive && setLive(false))
    tick()
    const id = setInterval(tick, 5000)
    return () => { alive = false; clearInterval(id) }
  }, [])
  return live
}

export const currentSession = () => read(SESSION, null)
export function logOut() {
  try { localStorage.removeItem(SESSION) } catch { /* nothing to clear */ }
}

export default function Auth({ onEnter }) {
  const { t } = useI18n()
  const [mode, setMode] = useState('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const signup = mode === 'signup'
  const live = useSensorLive()

  const switchMode = (next) => { setMode(next); setError('') }

  async function submit(e) {
    e.preventDefault()
    setError('')
    const key = email.trim().toLowerCase()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(key)) return setError(t('auth.errEmail'))
    if (password.length < 6) return setError(t('auth.errShort'))
    if (signup && !name.trim()) return setError(t('auth.errName'))
    setBusy(true)
    const accounts = read(ACCOUNTS, {})
    try {
      if (signup) {
        if (accounts[key]) return setError(t('auth.errTaken'))
        const salt = crypto.randomUUID()
        accounts[key] = { name: name.trim(), salt, hash: await hash(password, salt) }
        write(ACCOUNTS, accounts)
      } else {
        const acc = accounts[key]
        if (!acc || acc.hash !== await hash(password, acc.salt)) return setError(t('auth.errWrong'))
      }
      const session = { email: key, name: accounts[key].name }
      write(SESSION, session)
      onEnter(session)
    } finally {
      setBusy(false)
    }
  }

  const watchDemo = () => {
    if (DEMO_URL) window.open(DEMO_URL, '_blank', 'noopener')
    else onEnter({ guest: true })
  }

  return (
    <div className="auth">
      <header className="auth-top">
        <Logo />
        <LanguagePicker />
      </header>

      <main className="auth-main">
        <section className="card auth-card" aria-labelledby="auth-title">
          <h1 id="auth-title">{signup ? t('auth.signupTitle') : t('auth.loginTitle')}</h1>
          <p className="muted">{signup ? t('auth.signupSub') : t('auth.loginSub')}</p>

          <div className="auth-switch" role="tablist">
            <button type="button" role="tab" aria-selected={!signup} onClick={() => switchMode('login')}>{t('auth.login')}</button>
            <button type="button" role="tab" aria-selected={signup} onClick={() => switchMode('signup')}>{t('auth.signup')}</button>
          </div>

          <form className="auth-form" onSubmit={submit} noValidate>
            {signup && (
              <label>
                <span>{t('auth.name')}</span>
                <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
              </label>
            )}
            <label>
              <span>{t('auth.email')}</span>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" inputMode="email" />
            </label>
            <label>
              <span>{t('auth.password')}</span>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                autoComplete={signup ? 'new-password' : 'current-password'} />
            </label>
            {error && <p className="auth-error" role="alert">{error}</p>}
            <button className="btn btn-volt auth-submit" type="submit" disabled={busy}>
              {signup ? t('auth.signupBtn') : t('auth.loginBtn')}
            </button>
          </form>
        </section>

        <p className="auth-or" aria-hidden="true"><span>{t('auth.or')}</span></p>

        <section className="auth-event" aria-labelledby="event-title">
          <div className="auth-event-head">
            <p className="auth-event-label">NASA Space Apps Challenge 2026 · Skopje</p>
            {live && <span className="auth-live" role="status"><span className="dot" aria-hidden="true" />{t('auth.live')}</span>}
          </div>
          <h2 id="event-title">{t('auth.eventTitle')}</h2>
          <p className="auth-event-sub">{t('auth.eventSub')}</p>
          <button type="button" className="btn btn-ghost auth-watch" onClick={watchDemo}>
            {t('auth.watchDemo')}
            <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M5 12h14m-6-6 6 6-6 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </button>
        </section>
      </main>
    </div>
  )
}
