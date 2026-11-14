// Background artefact: field plots seen from above, square tiles tilted like the logo, a few with crop rows.
// Decorative tiles use solid theme colours so the pattern stays crisp in both themes.
const TILE = 64
const GAP = 8
const COLS = 18
const ROWS = 9

// fixed pattern (no randomness, so it never jumps between renders)
const kind = (r, c) => {
  const v = (r * 7 + c * 13 + r * c) % 11
  return v === 0 ? 'volt' : v < 4 ? 'rows' : v < 7 ? 'green' : 'plain'
}

export default function FarmGrid() {
  const tiles = []
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const x = c * (TILE + GAP)
      const y = r * (TILE + GAP)
      const k = kind(r, c)
      tiles.push(<rect key={`${r}-${c}`} x={x} y={y} width={TILE} height={TILE} rx="7" className={`plot plot-${k}`} />)
      if (k === 'rows') {
        for (let i = 1; i <= 3; i++) {
          const lx = x + (TILE * i) / 4
          tiles.push(<line key={`${r}-${c}-${i}`} x1={lx} y1={y + 10} x2={lx} y2={y + TILE - 10} className="plot-line" />)
        }
      }
    }
  }
  return (
    <div className="farm-grid" aria-hidden="true">
      <svg viewBox={`0 0 ${COLS * (TILE + GAP)} ${ROWS * (TILE + GAP)}`} preserveAspectRatio="xMidYMin slice">
        <g transform={`rotate(-20 ${(COLS * (TILE + GAP)) / 2} ${(ROWS * (TILE + GAP)) / 2})`}>{tiles}</g>
      </svg>
    </div>
  )
}
