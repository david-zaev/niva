import { useI18n } from '../i18n/index.jsx'

// Every screen: a plain title (its controls on the right on a PC) and the content.
export default function Screen({ section, eyebrow, actions, children }) {
  const { t } = useI18n()
  const brow = eyebrow ?? (t(`${section}.eyebrow`) !== `${section}.eyebrow` ? t(`${section}.eyebrow`) : null)
  return (
    <section className="screen">
      <header className="screen-head">
        <div>
          {brow && <p className="crumb">{brow}</p>}
          <h1>{t(`${section}.title`)}</h1>
          <p className="screen-sub">{t(`${section}.sub`)}</p>
        </div>
        {actions && <div className="head-actions">{actions}</div>}
      </header>
      {children}
    </section>
  )
}
