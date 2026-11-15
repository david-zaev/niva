// A stat card: a short label, one big number. `level` adds a colour AND a word (never colour alone).
import { useI18n } from '../i18n/index.jsx'

// `note` says where the number comes from; `empty` is shown when there is no number at all.
// `badge` marks a number from the farmer's own sensor: 'live' (fresh) or how long ago it was measured.
export default function SensorTile({ label, value, unit, digits = 0, level, levelText, bar = false, note, empty, badge }) {
  const { t } = useI18n()
  return (
    <div className={`card stat ${level ? `level-${level}` : ''} ${value == null ? 'is-empty' : ''}`}>
      <span className="stat-top">
        <span className="stat-label">{label}</span>
        {badge && (
          <span className={`stat-badge ${badge === 'live' ? 'is-live' : ''}`}>
            <span className="dot" aria-hidden="true" />{badge === 'live' ? t('field.liveShort') : badge}
          </span>
        )}
      </span>
      {value == null
        ? <span className="stat-empty">{empty ?? '—'}</span>
        : <span className="stat-value">{value.toFixed(digits)}<span className="stat-unit">{unit}</span></span>}
      {levelText && value != null && <span className="stat-status"><span className="dot" aria-hidden="true" />{levelText}</span>}
      {bar && value != null && (
        <div className="bar" aria-hidden="true">
          <span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
        </div>
      )}
      {note && value != null && <span className="stat-note">{note}</span>}
    </div>
  )
}
