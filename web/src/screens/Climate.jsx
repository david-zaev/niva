import Screen, { ComingSoon } from '../components/Screen.jsx'
import { useI18n } from '../i18n/index.jsx'

export default function Climate() {
  const { t } = useI18n()
  return (
    <Screen section="climate">
      <ComingSoon>{t('climate.empty')}</ComingSoon>
    </Screen>
  )
}
