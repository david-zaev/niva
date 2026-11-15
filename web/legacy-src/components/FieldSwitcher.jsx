import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { DEMO_FIELD, getField, getFields, isOwner, myFieldIds, openDemoFarm, paths, peek, switchField } from '../api.js'
import { useI18n } from '../i18n/index.jsx'
import { useCrops } from './util.js'

// Always shows which field the app is about; pick another, see them all on the map, or add one.
export default function FieldSwitcher({ current }) {
  const { t } = useI18n()
  const { cropName } = useCrops()
  const navigate = useNavigate()
  const box = useRef(null)
  const [fields, setFields] = useState(() => peek(paths.fields(myFieldIds()))?.fields ?? [])
  useEffect(() => {
    getFields().then((d) => setFields(d.fields)).catch(() => {})
  }, [current])
  useEffect(() => {
    const closeOutside = (e) => { if (!box.current?.contains(e.target)) box.current?.removeAttribute('open') }
    document.addEventListener('pointerdown', closeOutside)
    return () => document.removeEventListener('pointerdown', closeOutside)
  }, [])
  // a field opened from a link may not be in this phone's list: still show its name
  const [lone, setLone] = useState(() => peek(paths.field(current))?.name)
  useEffect(() => {
    getField(current).then((f) => setLone(f.name)).catch(() => {})
  }, [current])
  const close = () => box.current?.removeAttribute('open')
  const active = fields.find((f) => String(f.id) === String(current))
  const label = (f) => (String(f.id) === DEMO_FIELD ? t('switcher.demo') : f.name)
  const go = (path) => { close(); navigate(path) }

  return (
    <details className="field-switcher" ref={box} onKeyDown={(e) => { if (e.key === 'Escape') close() }}>
      <summary aria-label={t('switcher.label')}>
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21Z" /><circle cx="12" cy="9.5" r="2.5" /></svg>
        <span className="switcher-name">{active ? label(active) : lone ?? '…'}</span>
        <svg className="language-chevron" viewBox="0 0 20 20" width="14" height="14" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="m6 8 4 4 4-4" /></svg>
      </summary>
      <div className="switcher-menu" role="group" aria-label={t('switcher.label')}>
        <p className="switcher-title">{t('switcher.title')}</p>
        {fields.map((f) => (
          <button key={f.id} type="button" aria-pressed={String(f.id) === String(current)}
            onClick={() => { switchField(f.id); close() }}>
            <span className="switcher-row">
              <strong>{label(f)}</strong>
              <span className="muted small">
                {f.active_crop ? cropName(f.active_crop) : t('switcher.noCrop')}
                {!isOwner(String(f.id)) && ` · ${t('switcher.viewOnly')}`}
              </span>
            </span>
            {String(f.id) === String(current) && <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="m4 10 4 4 8-8" /></svg>}
          </button>
        ))}
        <div className="switcher-actions">
          {fields.length < 3 && <button type="button" className="btn btn-ghost" onClick={() => openDemoFarm().then(() => go('/'))}>{t('setup.demoBtn')}</button>}
        </div>
      </div>
    </details>
  )
}
