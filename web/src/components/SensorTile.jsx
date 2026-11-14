// A stat card: a short label, one big number. `level` adds a colour AND a word (never colour alone).
export default function SensorTile({ label, value, unit, digits = 0, level, levelText, bar = false }) {
  return (
    <div className={`card stat ${level ? `level-${level}` : ''}`}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">
        {value == null ? '—' : value.toFixed(digits)}
        {value != null && <span className="stat-unit">{unit}</span>}
      </span>
      {levelText && <span className="stat-status"><span className="dot" aria-hidden="true" />{levelText}</span>}
      {bar && value != null && (
        <div className="bar" aria-hidden="true">
          <span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
        </div>
      )}
    </div>
  )
}
