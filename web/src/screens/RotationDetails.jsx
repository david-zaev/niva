import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fieldId, ownerToken, patchField } from '../api.js'
import { ConfidencePill, MonthStrip, ScoreBars, StripLegend } from '../components/RotationCard.jsx'
import SellCard from '../components/SellCard.jsx'
import TermHelp from '../components/TermHelp.jsx'
import { useI18n } from '../i18n/index.jsx'
import { useRotations, useWhatIf } from './Rotations.jsx'

const HEADINGS = ['why', 'evidence', 'benefits', 'gaps', 'risks']

export default function RotationDetails() {
  const { id } = useParams()
  const { t } = useI18n()
  const { rain, temp, query } = useWhatIf()
  const { data, error } = useRotations(rain, temp)
  const r = data && [data.current, ...data.suggestions].find((x) => x.id === id)
  const [followed, setFollowed] = useState(null)
  const owner = ownerToken(fieldId()) != null
  // "I follow this rotation": it becomes the field's current rotation (scores, pests and the banner use it)
  const follow = () => patchField(fieldId(), { current_rotation: r.crops.map((c) => c.crop) })
    .then(() => setFollowed('ok')).catch(() => setFollowed('bad'))

  return (
    <section className="screen">
      <Link className="back" to={`/rotations${query}`}>← {t('rot.back')}</Link>
      {error && <p className="card">{t('server.down')}</p>}
      {data && !r && <p className="card">{t('rot.notFound')}</p>}
      {r && (
        <>
          <header className="screen-head">
            <span className={`pill ${r.kind === 'current' ? '' : 'pill-volt'}`}>{r.kind === 'current' ? t('rot.now') : t('rot.suggested')}</span>
            <h1>{r.name}</h1>
            <p className="screen-sub">
              {t('rot.total')}: <strong>{r.total}/100</strong>
              {(rain !== 0 || temp !== 0) && ` · ${t('rot.whatIf')}: ${rain > 0 ? '+' : ''}${rain}% ${t('rot.rain').toLowerCase()}, +${temp} °C`}
            </p>
            <span><ConfidencePill level={r.confidence} /> <TermHelp term="confidence" /></span>
            {r.kind !== 'current' && owner && <div className="row-btns">
              <button className="btn btn-volt" onClick={follow} disabled={followed === 'ok'}>{followed === 'ok' ? t('rot.following') : t('rot.follow')}</button>
            </div>}
            {followed === 'bad' && <p className="msg msg-bad">{t('crops.saveFailed')}</p>}
          </header>

          <div className="details-grid">
            <div className="card">
              <StripLegend />
              <MonthStrip strip={r.strip} crops={r.crops} />
              <ScoreBars scores={r.scores} help />
            </div>
            <div className="headings">
              {HEADINGS.map((h) => (
                <div className={`card heading heading-${h}`} key={h}>
                  <h2>{t(`rot.h_${h}`)}</h2>
                  {Array.isArray(r[h]) ? <ul>{r[h].map((line, i) => <li key={i}>{line}</li>)}</ul> : <p>{r[h]}</p>}
                </div>
              ))}
              <SellCard crops={r.crops} region={data.location.id} />
            </div>
          </div>
          <p className="source">{data.sources.map((s) => `${s.dataset} (${s.dates})`).join(' · ')}</p>
          <p className="disclaimer">{t('disclaimer')}</p>
        </>
      )}
    </section>
  )
}
