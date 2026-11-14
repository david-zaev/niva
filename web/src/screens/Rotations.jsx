import Screen, { ComingSoon } from '../components/Screen.jsx'
import { useI18n } from '../i18n/index.jsx'

export default function Rotations() {
  const { t } = useI18n()
  return (
    <Screen section="rotations">
      <ComingSoon>{t('rotations.empty')}</ComingSoon>
    </Screen>
  )
}
