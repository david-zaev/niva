import { useState } from 'react'

// Small SVG charts in the app's own style: thin marks, rounded bar ends on the baseline, recessive grid,
// hover tooltips, one y-axis. Colours come from CSS tokens (--series-1, --series-2) so dark mode works.

const W = 640

function ticks(max, n = 4) {
  if (max <= 0) return [0]
  const raw = max / n
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw)
  const out = []
  for (let v = 0; v <= max + 1e-9; v += step) out.push(+v.toFixed(6))
  return out
}

function Tip({ tip }) {
  if (!tip) return null
  return (
    <div className="chart-tip" style={{ left: `${(tip.x / W) * 100}%`, top: tip.y }}>
      {tip.lines.map((l, i) => <div key={i} className={i === 0 ? 'tip-head' : ''}>{l}</div>)}
    </div>
  )
}

// Grouped bars: categories along x, up to two series. series = [{name, key, color}]
export function Bars({ data, label, series, unit = '', height = 220, labelKey = 'label' }) {
  const [tip, setTip] = useState(null)
  const H = height
  const pad = { l: 40, r: 8, t: 12, b: 28 }
  const max = Math.max(1, ...data.flatMap((d) => series.map((s) => d[s.key] ?? 0)))
  const tk = ticks(max)
  const top = tk[tk.length - 1]
  const iw = W - pad.l - pad.r
  const ih = H - pad.t - pad.b
  const bw = iw / data.length
  const gap = 2
  const barW = Math.max(3, (bw * 0.7 - gap * (series.length - 1)) / series.length)
  const y = (v) => pad.t + ih - (v / top) * ih
  return (
    <div className="chart">
      {series.length > 1 && (
        <div className="legend">{series.map((s) => <span key={s.key}><i style={{ background: s.color }} />{s.name}</span>)}</div>
      )}
      <div className="chart-box">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} onMouseLeave={() => setTip(null)}>
          {tk.map((t) => (
            <g key={t}>
              <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} className="grid" />
              <text x={pad.l - 6} y={y(t) + 4} className="axis" textAnchor="end">{t}</text>
            </g>
          ))}
          {data.map((d, i) => {
            const x0 = pad.l + i * bw + (bw - (barW * series.length + gap * (series.length - 1))) / 2
            return (
              <g key={i}>
                {series.map((s, k) => {
                  const v = d[s.key] ?? 0
                  const h = Math.max(0, (v / top) * ih)
                  const x = x0 + k * (barW + gap)
                  const r = Math.min(4, barW / 2, h)
                  return <path key={s.key} fill={s.color}
                    d={`M${x},${pad.t + ih} V${pad.t + ih - h + r} Q${x},${pad.t + ih - h} ${x + r},${pad.t + ih - h} H${x + barW - r} Q${x + barW},${pad.t + ih - h} ${x + barW},${pad.t + ih - h + r} V${pad.t + ih} Z`} />
                })}
                <text x={pad.l + i * bw + bw / 2} y={H - 8} className="axis" textAnchor="middle">{d[labelKey]}</text>
                <rect x={pad.l + i * bw} y={pad.t} width={bw} height={ih} fill="transparent"
                  onMouseEnter={() => setTip({ x: pad.l + i * bw + bw / 2, y: 4,
                    lines: [String(d.tip ?? d[labelKey]), ...series.map((s) => `${s.name}: ${d[s.key] ?? '–'}${unit}`)] })} />
              </g>
            )
          })}
        </svg>
        <Tip tip={tip} />
      </div>
    </div>
  )
}

// Line over x (numbers or dates). lines = [{name, color, points: [{x, y}]}]; bands = [{y, label}] reference lines
export function Lines({ lines, label, height = 220, yMax, yMin = 0, xFormat = (v) => v, yUnit = '', refs = [] }) {
  const [tip, setTip] = useState(null)
  const H = height
  const pad = { l: 40, r: 10, t: 12, b: 28 }
  const all = lines.flatMap((l) => l.points)
  if (!all.length) return <p className="muted small">No data yet.</p>
  const xs = all.map((p) => +p.x)
  const x0 = Math.min(...xs)
  const x1 = Math.max(...xs) || x0 + 1
  const top = yMax ?? Math.max(...all.map((p) => p.y), ...refs.map((r) => r.y)) * 1.1
  const iw = W - pad.l - pad.r
  const ih = H - pad.t - pad.b
  const X = (v) => pad.l + ((+v - x0) / (x1 - x0 || 1)) * iw
  const Y = (v) => pad.t + ih - ((v - yMin) / (top - yMin || 1)) * ih
  const tk = ticks(top - yMin).map((t) => t + yMin)
  const xt = [0, 0.25, 0.5, 0.75, 1].map((f) => x0 + f * (x1 - x0))
  const onMove = (e) => {
    const box = e.currentTarget.getBoundingClientRect()
    const fx = ((e.clientX - box.left) / box.width) * W
    const xv = x0 + ((fx - pad.l) / iw) * (x1 - x0)
    const near = lines.map((l) => l.points.reduce((a, b) => (Math.abs(+b.x - xv) < Math.abs(+a.x - xv) ? b : a), l.points[0]))
    if (!near[0]) return
    setTip({ x: X(near[0].x), y: 4, lines: [String(xFormat(near[0].x)), ...near.map((p, i) => `${lines[i].name}: ${p.y}${yUnit}`)] })
  }
  return (
    <div className="chart">
      {lines.length > 1 && (
        <div className="legend">{lines.map((l) => <span key={l.name}><i style={{ background: l.color }} />{l.name}</span>)}</div>
      )}
      <div className="chart-box">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} onMouseMove={onMove} onMouseLeave={() => setTip(null)}>
          {tk.map((t) => (
            <g key={t}>
              <line x1={pad.l} x2={W - pad.r} y1={Y(t)} y2={Y(t)} className="grid" />
              <text x={pad.l - 6} y={Y(t) + 4} className="axis" textAnchor="end">{+t.toFixed(2)}</text>
            </g>
          ))}
          {xt.map((v, i) => <text key={i} x={X(v)} y={H - 8} className="axis" textAnchor={i === 0 ? 'start' : i === 4 ? 'end' : 'middle'}>{xFormat(v)}</text>)}
          {refs.map((r) => (
            <g key={r.label}>
              <line x1={pad.l} x2={W - pad.r} y1={Y(r.y)} y2={Y(r.y)} className="ref" />
              <text x={W - pad.r} y={Y(r.y) - 4} className="axis" textAnchor="end">{r.label}</text>
            </g>
          ))}
          {lines.map((l) => (
            <polyline key={l.name} fill="none" stroke={l.color} strokeWidth="2" strokeLinejoin="round"
              points={l.points.map((p) => `${X(p.x)},${Y(p.y)}`).join(' ')} />
          ))}
          {tip && <line x1={tip.x} x2={tip.x} y1={pad.t} y2={pad.t + ih} className="cross" />}
        </svg>
        <Tip tip={tip} />
      </div>
    </div>
  )
}
