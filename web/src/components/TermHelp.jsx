import { useEffect, useId, useRef, useState } from 'react'
import { useI18n } from '../i18n/index.jsx'

// The "?" next to a word: tap it for a one-line explanation (help.<term> in en.json / mk.json)
export default function TermHelp({ term }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState(null)
  const id = useId()
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return
    const close = (e) => !ref.current?.contains(e.target) && setOpen(false)
    const esc = (e) => e.key === 'Escape' && setOpen(false)
    const shut = () => setOpen(false)
    document.addEventListener('pointerdown', close)
    document.addEventListener('keydown', esc)
    window.addEventListener('scroll', shut, { passive: true })
    window.addEventListener('resize', shut)
    return () => {
      document.removeEventListener('pointerdown', close)
      document.removeEventListener('keydown', esc)
      window.removeEventListener('scroll', shut)
      window.removeEventListener('resize', shut)
    }
  }, [open])
  return (
    <span className="term-help" ref={ref}>
      <button type="button" className="help-btn" aria-expanded={open} aria-controls={id}
        aria-label={t('help.what')} onClick={(e) => {
          e.preventDefault()
          // fixed position, kept inside the screen with a 12 px margin
          const r = e.currentTarget.getBoundingClientRect()
          const w = Math.min(280, window.innerWidth - 24)
          setPos({ top: r.bottom + 8, left: Math.min(Math.max(12, r.left + r.width / 2 - w / 2), window.innerWidth - w - 12), width: w })
          setOpen((o) => !o)
        }}>?</button>
      {open && pos && <span id={id} role="note" className="help-pop" style={pos}>{t(`help.${term}`)}</span>}
    </span>
  )
}
