import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { DEMO_FIELD, fieldId, getField, ownerToken, pairDevice, patchField, paths, peek, selectField } from '../api.js'
import { PrioritySliders, RotationPicker } from '../components/FieldForms.jsx'
import QrScanner, { canScan } from '../components/QrScanner.jsx'
import Screen from '../components/Screen.jsx'
import { useI18n } from '../i18n/index.jsx'
import { canInstall, install, isInstalled, isIos, onInstallable } from '../pwa.js'

function MyFieldCard({ field }) {
  const { t } = useI18n()
  const id = fieldId()
  const switchTo = (to) => {
    selectField(to)
    location.reload()
  }
  return (
    <div className="card setting">
      <span className="label">{t('more.myField')}</span>
      <p className="setting-main">{field ? field.name : '…'}</p>
      {field && <p className="muted small">{field.lat}, {field.lon}{id === DEMO_FIELD ? ` · ${t('more.demo')}` : ''}</p>}
      <div className="row-btns">
        <Link className="btn" to="/setup">{t(ownerToken() ? 'more.anotherField' : 'more.newField')}</Link>
        {id !== DEMO_FIELD && <button className="btn btn-ghost" onClick={() => switchTo(DEMO_FIELD)}>{t('more.showDemo')}</button>}
      </div>
    </div>
  )
}

function SensorCard({ owner }) {
  const { t } = useI18n()
  const [scan, setScan] = useState(false)
  const [d, setD] = useState('')
  const [c, setC] = useState('')
  const [msg, setMsg] = useState(null)
  const pair = async (dev, code) => {
    setScan(false)
    setMsg({ kind: 'wait', text: t('field.loading') })
    try {
      await pairDevice(fieldId(), dev.trim().toUpperCase(), code.trim().toUpperCase())
      setMsg({ kind: 'ok', text: t('pair.done') })
    } catch (e) {
      setMsg({ kind: 'bad', text: t(e.status === 404 ? 'pair.wrong' : 'pair.failed') })
    }
  }
  return (
    <div className="card setting" id="sensor">
      <span className="label">{t('more.addSensor')}</span>
      {!owner ? <p className="muted">{t('more.ownerOnly')}</p> : (
        <>
          <p className="muted small">{t('more.sensorHelp')}</p>
          {scan ? <QrScanner onCode={pair} onClose={() => setScan(false)} /> : (
            <form className="pair-form" onSubmit={(e) => { e.preventDefault(); pair(d, c) }}>
              {canScan && <button type="button" className="btn btn-volt" onClick={() => setScan(true)}>{t('more.scan')}</button>}
              <label className="text-input"><span className="label">{t('more.deviceId')}</span>
                <input value={d} onChange={(e) => setD(e.target.value)} placeholder="NIVA-A1F3" autoCapitalize="characters" /></label>
              <label className="text-input"><span className="label">{t('more.pairCode')}</span>
                <input value={c} onChange={(e) => setC(e.target.value)} placeholder="K7Q2XM" autoCapitalize="characters" /></label>
              <button className="btn" disabled={!d.trim() || !c.trim()}>{t('more.pair')}</button>
            </form>
          )}
          {msg && <p className={`msg msg-${msg.kind}`} role="status">{msg.text}</p>}
        </>
      )}
    </div>
  )
}

function FarmCard({ field, owner, onSaved }) {
  const { t } = useI18n()
  const [rotation, setRotation] = useState(field.current_rotation ?? [])
  const [priorities, setPriorities] = useState(field.priorities ?? {})
  const [msg, setMsg] = useState(null)
  if (!owner) return null
  const saveIt = async () => {
    setMsg(t('field.loading'))
    try {
      onSaved(await patchField(field.id, { current_rotation: rotation, priorities }))
      setMsg(t('more.saved'))
    } catch {
      setMsg(t('server.down'))
    }
  }
  return (
    <div className="card setting">
      <span className="label">{t('more.yourRotation')}</span>
      <RotationPicker value={rotation} onChange={setRotation} />
      <span className="label spaced">{t('more.priorities')}</span>
      <PrioritySliders value={priorities} onChange={setPriorities} />
      <div className="row-btns">
        <button className="btn" onClick={saveIt}>{t('more.save')}</button>
        {msg && <span className="muted" role="status">{msg}</span>}
      </div>
    </div>
  )
}

function InstallCard() {
  const { t } = useI18n()
  const [ready, setReady] = useState(canInstall())
  useEffect(() => onInstallable(setReady), [])
  if (isInstalled()) return null
  return (
    <div className="card setting">
      <span className="label">{t('more.install')}</span>
      {ready ? <button className="btn btn-volt" onClick={install}>{t('more.installBtn')}</button>
        : <p className="muted small">{isIos() ? t('more.installIos') : t('more.installOther')}</p>}
    </div>
  )
}

const DATA = ['power', 'soil', 'makstat', 'zpis', 'osm']

export default function More({ theme, setTheme }) {
  const { t, lang, setLang } = useI18n()
  const [field, setField] = useState(() => peek(paths.field(fieldId())))
  const owner = !!ownerToken()
  useEffect(() => {
    getField(fieldId()).then(setField).catch(() => {})
  }, [])
  return (
    <Screen section="more">
      <div className="settings-grid">
        <MyFieldCard field={field} />
        <SensorCard owner={owner} />
        {field && <FarmCard key={field.id} field={field} owner={owner} onSaved={setField} />}
        <div className="card setting">
          <span className="label">{t('more.language')}</span>
          <div className="segmented">
            <button aria-pressed={lang === 'mk'} onClick={() => setLang('mk')}>Македонски</button>
            <button aria-pressed={lang === 'en'} onClick={() => setLang('en')}>English</button>
          </div>
          <span className="label spaced">{t('more.theme')}</span>
          <div className="segmented">
            {['auto', 'light', 'dark'].map((mode) => (
              <button key={mode} aria-pressed={theme === mode} onClick={() => setTheme(mode)}>
                {t(`more.theme${mode[0].toUpperCase()}${mode.slice(1)}`)}
              </button>
            ))}
          </div>
        </div>
        <InstallCard />
        <div className="card setting about">
          <span className="label">{t('more.about')}</span>
          <ul>{DATA.map((k) => <li key={k}>{t(`more.data_${k}`)}</li>)}</ul>
          <p className="muted small">{t('more.aboutNote')}</p>
        </div>
      </div>
    </Screen>
  )
}
