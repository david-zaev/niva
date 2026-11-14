import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getRotations } from '../api.js'
import RotationCard, { StripLegend } from '../components/RotationCard.jsx'
import Screen from '../components/Screen.jsx'
import TermHelp from '../components/TermHelp.jsx'
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
  return { rain, temp, set, query }
}

export function useRotations(rain, temp) {
  const fieldId = load('niva.fieldId', '1')
  const [state, setState] = useState({ data: null, error: false, loading: true })
  useEffect(() => {
    let alive = true
    setState((s) => ({ ...s, loading: true }))
    const id = setTimeout(() => {
      getRotations(fieldId, rain, temp)
        .then((data) => alive && setState({ data, error: false, loading: false }))
        .catch(() => alive && setState((s) => ({ ...s, error: true, loading: false })))
    }, 150) // small debounce while a slider moves
    return () => {
      alive = false
      clearTimeout(id)
    }
  }, [fieldId, rain, temp])
  return state
}

function WhatIf({ rain, temp, set }) {
  const { t } = useI18n()
  return (
    <div className="card whatif">
      <span className="label">{t('rot.whatIf')} <TermHelp term="whatIf" /></span>
      <label className="slider">
        <span>{t('rot.rain')} <strong>{rain > 0 ? '+' : ''}{rain}%</strong></span>
        <input type="range" min="-40" max="20" step="10" value={rain} onChange={(e) => set('rain', e.target.value)} />
      </label>
      <label className="slider">
        <span>{t('rot.temp')} <strong>+{temp} °C</strong></span>
        <input type="range" min="0" max="3" step="1" value={temp} onChange={(e) => set('temp', e.target.value)} />
      </label>
    </div>
  )
}

export default function Rotations() {
  const { t } = useI18n()
  const { rain, temp, set, query } = useWhatIf()
  const { data, error, loading } = useRotations(rain, temp)

  return (
    <Screen section="rotations">
      <WhatIf rain={rain} temp={temp} set={set} />
      {error && <p className="card">{t('server.down')}</p>}
      {!data && !error && <p className="card muted">{t('field.loading')}</p>}
      {data && (
        <>
          {data.current_is_default && <p className="note">{t('rot.defaultCurrent')}</p>}
          <StripLegend />
          <div className={`rot-grid ${loading ? 'is-loading' : ''}`}>
            {[data.current, ...data.suggestions].map((r) => <RotationCard key={r.id} r={r} query={query} />)}
          </div>
          <p className="source">{data.sources.map((s) => `${s.dataset} (${s.dates})`).join(' · ')}</p>
        </>
      )}
    </Screen>
  )
}
