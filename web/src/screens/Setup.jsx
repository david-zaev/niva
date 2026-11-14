import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createField, pairDevice } from '../api.js'
import { FieldMap, PrioritySliders, RotationPicker } from '../components/FieldForms.jsx'
import { load, save, useI18n } from '../i18n/index.jsx'

// First run of a farmer's own field: language → tap the field → current rotation → priorities → save.
// The phone that creates the field keeps its owner token (no accounts this weekend, DESIGN.md).
export default function Setup() {
  const { t, lang, setLang } = useI18n()
  const nav = useNavigate()
  const [step, setStep] = useState(0)
  const [name, setName] = useState('')
  const [point, setPoint] = useState(null)
  const [rotation, setRotation] = useState([])
  const [priorities, setPriorities] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const steps = ['language', 'place', 'rotation', 'priorities']
  const canNext = step !== 1 || (point && name.trim())

  async function finish() {
    setBusy(true)
    setError(null)
    try {
      const f = await createField({ name: name.trim(), lat: point.lat, lon: point.lon, current_rotation: rotation, priorities })
      let pending = null
      try {
        pending = JSON.parse(load('niva.pendingPair', 'null'))
      } catch { /* none */ }
      if (pending) {
        save('niva.pendingPair', 'null')
        await pairDevice(f.id, pending.d, pending.c).catch(() => {})
      }
      nav('/')
    } catch {
      setError(t('server.down'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="screen setup">
      <header className="screen-head">
        <span className="pill">{t('setup.stepOf').replace('{n}', step + 1).replace('{m}', steps.length)}</span>
        <h1>{t(`setup.title_${steps[step]}`)}</h1>
        <p className="screen-sub">{t(`setup.sub_${steps[step]}`)}</p>
      </header>

      <div className="card">
        {step === 0 && (
          <div className="segmented big">
            <button aria-pressed={lang === 'mk'} onClick={() => setLang('mk')}>Македонски</button>
            <button aria-pressed={lang === 'en'} onClick={() => setLang('en')}>English</button>
          </div>
        )}
        {step === 1 && (
          <>
            <label className="text-input">
              <span className="label">{t('setup.name')}</span>
              <input value={name} maxLength={80} placeholder={t('setup.namePlaceholder')} onChange={(e) => setName(e.target.value)} />
            </label>
            <FieldMap value={point} onChange={setPoint} />
          </>
        )}
        {step === 2 && <RotationPicker value={rotation} onChange={setRotation} />}
        {step === 3 && <PrioritySliders value={priorities} onChange={setPriorities} />}
      </div>

      {error && <p className="card error">{error}</p>}
      <div className="wizard-nav">
        {step > 0 ? <button className="btn btn-ghost" onClick={() => setStep(step - 1)}>← {t('setup.back')}</button> : <span />}
        {step < steps.length - 1
          ? <button className="btn" disabled={!canNext} onClick={() => setStep(step + 1)}>{t('setup.next')} →</button>
          : <button className="btn btn-volt" disabled={busy} onClick={finish}>{busy ? t('field.loading') : t('setup.save')}</button>}
      </div>
      <p className="disclaimer">{t('disclaimer')}</p>
    </section>
  )
}
