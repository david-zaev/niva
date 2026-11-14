import Screen from '../components/Screen.jsx'
import { useI18n } from '../i18n/index.jsx'

export default function More({ theme, setTheme }) {
  const { t, lang, setLang } = useI18n()
  return (
    <Screen title={t('more.title')}>
      <div className="card setting">
        <span className="label">{t('more.language')}</span>
        <div className="segmented">
          <button aria-pressed={lang === 'mk'} onClick={() => setLang('mk')}>Македонски</button>
          <button aria-pressed={lang === 'en'} onClick={() => setLang('en')}>English</button>
        </div>
      </div>
      <div className="card setting">
        <span className="label">{t('more.theme')}</span>
        <div className="segmented">
          {['auto', 'light', 'dark'].map((mode) => (
            <button key={mode} aria-pressed={theme === mode} onClick={() => setTheme(mode)}>
              {t(`more.theme${mode[0].toUpperCase()}${mode.slice(1)}`)}
            </button>
          ))}
        </div>
      </div>
      <p className="card muted">{t('more.empty')}</p>
    </Screen>
  )
}
