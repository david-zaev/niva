import { useEffect, useRef } from 'react'
import { useI18n } from '../i18n/index.jsx'

const languages = [{ code: 'en', name: 'English' }, { code: 'mk', name: 'Македонски' }]

export default function LanguagePicker() {
  const { t, lang, setLang } = useI18n()
  const picker = useRef(null)
  useEffect(() => {
    const closeOutside = (event) => {
      if (!picker.current?.contains(event.target)) picker.current?.removeAttribute('open')
    }
    document.addEventListener('pointerdown', closeOutside)
    return () => document.removeEventListener('pointerdown', closeOutside)
  }, [])
  const close = () => {
    picker.current.removeAttribute('open')
    picker.current.querySelector('summary').focus()
  }
  return (
    <details className="language-picker" ref={picker}
      onKeyDown={(event) => { if (event.key === 'Escape') close() }}
      onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.removeAttribute('open') }}>
      <summary aria-label={t('more.language')}>
        <svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a18 18 0 0 1 0 18 18 18 0 0 1 0-18Z" />
        </svg>
        <span>{languages.find((language) => language.code === lang)?.name ?? 'English'}</span>
        <svg className="language-chevron" viewBox="0 0 20 20" width="14" height="14" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="m6 8 4 4 4-4" /></svg>
      </summary>
      <div className="language-options" role="group" aria-label={t('more.language')}>
        {languages.map(({ code, name }) => (
          <button key={code} type="button" lang={code} aria-pressed={lang === code}
            onClick={() => { setLang(code); close() }}>
            <span>{name}</span>
            {lang === code && <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="m4 10 4 4 8-8" /></svg>}
          </button>
        ))}
      </div>
    </details>
  )
}
