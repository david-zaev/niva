// One big number with its unit and label. `level` adds a colour AND a word (never colour alone).
export default function SensorTile({ label, value, unit, digits = 0, level, levelText, big = false }) {
  return (
    <div className={`card tile ${big ? 'tile-big' : ''} ${level ? `level-${level}` : ''}`}>
      <span className="label">{label}</span>
      <span className="tile-value">
        {value.toFixed(digits)}
        <span className="tile-unit">{unit}</span>
      </span>
      {levelText && <span className="tile-level">{levelText}</span>}
    </div>
  )
}
