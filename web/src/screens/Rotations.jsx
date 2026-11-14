import Screen from '../components/Screen.jsx'
import { useI18n } from '../i18n/index.jsx'

export default function Rotations() {
  const { t } = useI18n()
  return (
    <Screen title={t('rotations.title')}>
      <p className="card muted">{t('rotations.empty')}</p>
    </Screen>
  )
}
