import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { getRotations, paths, peek } from '../api.js'
import { ModeToggle, useMode } from '../components/Mode.jsx'
import RotationCard, { SCORE_KEYS, StripLegend } from '../components/RotationCard.jsx'
import Screen from '../components/Screen.jsx'
import { load, useI18n } from '../i18n/index.jsx'

// What-if sliders live in the URL so the details page and a shared link see the same scenario
export function useWhatIf() {
  const [params, setParams] = useSearchParams()
  const rain = Number(params.get('rain') ?? 0)
  const temp = Number(params.get('temp') ?? 0)
  const set = (k, v) => {
    const next = new URLSearchParams(params)
    if (Number(v) === 0) next.delete(k)
    else next.set(k, v)
    setParams(next, { replace: true })
  }
  const query = params.toString() ? `?${params}` : ''
  const reset = () => {
    const next = new URLSearchParams(params)
    next.delete('rain')
    next.delete('temp')
    setParams(next, { replace: true })
  }
  return { rain, temp, set, reset, query }
}

export function useRotations(rain, temp) {
  const fieldId = load('niva.fieldId', '1')
  const [state, setState] = useState(() => {
    const data = peek(paths.rotations(fieldId, rain, temp))
    return { data, error: false, loading: !data }
  })
  useEffect(() => {
    let alive = true
    const hit = peek(paths.rotations(fieldId, rain, temp))
    setState((s) => ({ data: hit ?? s.data, error: false, loading: !hit }))
    const id = setTimeout(() => {
      getRotations(fieldId, rain, temp)
        .then((data) => alive && setState({ data, error: false, loading: false }))
        .catch(() => alive && setState((s) => ({ ...s, error: true, loading: false })))
    }, hit ? 0 : 150) // small debounce while a slider moves
    return () => {
      alive = false
      clearTimeout(id)
    }
  }, [fieldId, rain, temp])
  return state
}

function WhatIf({ rain, temp, set, reset }) {
  const { t } = useI18n()
  const changed = rain !== 0 || temp !== 0
  return (
    <details className="whatif">
      <summary>
        <svg className="scenario-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
          <path d="M4 7h16M4 17h16" /><circle cx="9" cy="7" r="3" fill="var(--canvas)" /><circle cx="15" cy="17" r="3" fill="var(--canvas)" />
        </svg>
        <span className="scenario-title">{t('rot.scenario')}</span>
        {changed && <span className="scenario-status">{t('rot.rain')} {rain > 0 ? '+' : ''}{rain}% · +{temp} °C</span>}
        <svg className="scenario-chevron" viewBox="0 0 20 20" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="m6 8 4 4 4-4" /></svg>
      </summary>
      <div className="scenario-body">
        <p className="scenario-help">{t('rot.scenarioHelp')}</p>
        <div className="scenario-controls">
          <label className="slider scenario-slider">
            <span className="scenario-label"><span>{t('rot.rain')}</span><output>{rain > 0 ? '+' : ''}{rain}%</output></span>
            <input aria-label={t('rot.rain')} type="range" min="-40" max="20" step="10" value={rain} style={{ '--range-progress': `${(rain + 40) / 60 * 100}%` }} onChange={(e) => set('rain', e.target.value)} />
            <span className="range-limits" aria-hidden="true"><span>−40%</span><span>+20%</span></span>
          </label>
          <label className="slider scenario-slider">
            <span className="scenario-label"><span>{t('rot.temp')}</span><output>+{temp} °C</output></span>
            <input aria-label={t('rot.temp')} type="range" min="0" max="3" step="1" value={temp} style={{ '--range-progress': `${temp / 3 * 100}%` }} onChange={(e) => set('temp', e.target.value)} />
            <span className="range-limits" aria-hidden="true"><span>0 °C</span><span>+3 °C</span></span>
          </label>
          <button type="button" className="scenario-reset" disabled={!changed} onClick={reset}>{t('rot.resetScenario')}</button>
        </div>
      </div>
    </details>
  )
}

// Advanced: every score side by side, and how much of each crop the region grows (MakStat)
function Compare({ data }) {
  const { t, lang } = useI18n()
  const all = [data.current, ...data.suggestions]
  const trend = data.regional_trend?.crops ?? {}
  const crops = [...new Map(all.flatMap((r) => r.crops).map((c) => [c.crop, c])).values()]
  return (
    <div className="chart-grid">
      <article className="card">
        <div className="card-head"><h2>{t('rot.compareTitle')}</h2></div>
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>{t('rot.rotation')}</th><th>{t('rot.total')}</th>{SCORE_KEYS.map((k) => <th key={k}>{t(`rot.score_${k}`)}</th>)}</tr></thead>
            <tbody>{all.map((r) => (
              <tr key={r.id} className={r.kind === 'current' ? 'is-current' : ''}>
                <td><Link to={`/rotations/${r.id}`}>{r.name}</Link></td><td><strong>{r.total}</strong></td>
                {SCORE_KEYS.map((k) => <td key={k}>{r.scores[k]}</td>)}
              </tr>
            ))}</tbody>
          </table>
        </div>
      </article>
      <article className="card">
        <div className="card-head"><h2>{t('rot.trendTitle')}</h2></div>
        <p className="chart-help">{t('rot.trendHelp')}</p>
        <ul className="trend-list">{crops.map((c) => {
          const tr = trend[c.crop]
          return (
            <li key={c.crop}>
              <span>{lang === 'mk' ? c.name_mk : c.name}</span>
              {tr ? <span className={`trend trend-${tr.direction}`}>{tr.direction === 'up' ? '▲' : tr.direction === 'down' ? '▼' : '■'} {tr.production_change_pct > 0 ? '+' : ''}{tr.production_change_pct}% <span className="muted small">({tr.before_years} → {tr.last_years})</span></span>
                : <span className="muted small">{t('market.noData')}</span>}
            </li>
          )
        })}</ul>
        <p className="source">MakStat · {t('market.soldMissing')}</p>
      </article>
    </div>
  )
}

export default function Rotations() {
  const { t } = useI18n()
  const { rain, temp, set, reset, query } = useWhatIf()
  const { data, error, loading } = useRotations(rain, temp)
  const [mode, setMode] = useMode('rotations')

  return (
    <Screen section="rotations" actions={<ModeToggle mode={mode} setMode={setMode} />}>
      {mode === 'advanced' && <WhatIf rain={rain} temp={temp} set={set} reset={reset} />}
      {error && <p className="card">{t('server.down')}</p>}
      {!data && !error && <p className="card muted">{t('field.loading')}</p>}
      {data && (
        <>
          {data.current_is_default && <p className="note">{t('rot.defaultCurrent')}</p>}
          <StripLegend />
          <div className={`rot-grid ${loading ? 'is-loading' : ''}`}>
            {[data.current, ...data.suggestions].map((r) => <RotationCard key={r.id} r={r} query={query} />)}
          </div>
          {mode === 'advanced' && <Compare data={data} />}
          <p className="source">{data.sources.map((s) => `${s.dataset} (${s.dates})`).join(' · ')}</p>
        </>
      )}
    </Screen>
  )
}
