import Screen from '../components/Screen.jsx'
import { useI18n } from '../i18n/index.jsx'

export default function Climate() {
  const { t } = useI18n()
  return (
    <Screen title={t('climate.title')}>
      <p className="card muted">{t('climate.empty')}</p>
    </Screen>
  )
}
