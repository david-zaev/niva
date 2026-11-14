import { useI18n } from '../i18n/index.jsx'

// Every screen: a title, its content, and the line that Niva supports, not replaces, the farmer.
export default function Screen({ title, children }) {
  const { t } = useI18n()
  return (
    <section className="screen">
      <h1>{title}</h1>
      {children}
      <p className="disclaimer">{t('disclaimer')}</p>
    </section>
  )
}
