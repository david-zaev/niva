import Screen from '../components/Screen.jsx'
import ServerStatus from '../components/ServerStatus.jsx'
import { useI18n } from '../i18n/index.jsx'

export default function MyField() {
  const { t } = useI18n()
  return (
    <Screen title={t('field.title')}>
      <ServerStatus />
      <p className="card muted">{t('field.empty')}</p>
    </Screen>
  )
}
