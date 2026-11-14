import { useI18n } from '../i18n/index.jsx'

// Puts the `mark` part of the title on a volt highlight, like "My <field>".
function Title({ text, mark }) {
  const i = mark ? text.indexOf(mark) : -1
  if (i < 0) return <h1>{text}</h1>
  return (
    <h1>
      {text.slice(0, i)}
      <span className="mark">{mark}</span>
      {text.slice(i + mark.length)}
    </h1>
  )
}

// Every screen: a header, its content, and the line that Niva supports, not replaces, the farmer.
export default function Screen({ section, children }) {
  const { t } = useI18n()
  return (
    <section className="screen">
      <header className="screen-head">
        {t(`${section}.eyebrow`) !== `${section}.eyebrow` && <span className="pill">{t(`${section}.eyebrow`)}</span>}
        <Title text={t(`${section}.title`)} mark={t(`${section}.mark`)} />
        <p className="screen-sub">{t(`${section}.sub`)}</p>
      </header>
      {children}
      <p className="disclaimer">{t('disclaimer')}</p>
    </section>
  )
}

// Dashed placeholder for parts that come in a later milestone
export function ComingSoon({ children }) {
  return (
    <div className="card coming">
      <span className="pill">Soon</span>
      <p>{children}</p>
    </div>
  )
}
