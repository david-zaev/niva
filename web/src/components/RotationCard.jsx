import { Link } from 'react-router-dom'
import { useI18n } from '../i18n/index.jsx'

export const SCORE_KEYS = ['water', 'soil', 'erosion', 'pest', 'climate', 'income']
const MONTH_LETTERS = { en: 'JFMAMJJASOND', mk: 'ЈФМАМЈЈАСОНД' }
const monthName = (m, lang) => new Date(2001, m - 1, 1).toLocaleString(lang === 'mk' ? 'mk-MK' : 'en-GB', { month: 'long' })

// 12 blocks per rotation year: crop, bare, or bare in a storm month (risk). Never colour alone: a legend
// names the states and each block has a title.
export function MonthStrip({ strip, crops }) {
  const { t, lang } = useI18n()
  const name = (id) => {
    const c = crops.find((x) => x.crop === id)
    return c ? (lang === 'mk' ? c.name_mk : c.name) : ''
  }
  return (
    <div className="strip" role="img" aria-label={t('rot.stripLabel')}>
      <div className="strip-row strip-head" aria-hidden="true">
        <span className="strip-year" />
        {[...MONTH_LETTERS[lang]].map((m, i) => <span key={i} className="strip-m">{m}</span>)}
      </div>
      {strip.map((row, y) => (
        <div className="strip-row" key={y}>
          <span className="strip-year">{t('rot.yearShort')}{y + 1}</span>
          {row.map((cell) => (
            <span key={cell.month} className={`cell cell-${cell.state}`}
              title={`${t('rot.yearShort')}${y + 1} · ${monthName(cell.month, lang)}: ${cell.crop ? name(cell.crop) : t(`rot.state_${cell.state}`)}`} />
          ))}
        </div>
      ))}
    </div>
  )
}

export function StripLegend() {
  const { t } = useI18n()
  return (
    <div className="strip-legend">
      {['crop', 'bare', 'risk'].map((s) => (
        <span key={s}><span className={`cell cell-${s}`} aria-hidden="true" />{t(`rot.state_${s}`)}</span>
      ))}
    </div>
  )
}

export function ScoreBars({ scores }) {
  const { t } = useI18n()
  return (
    <ul className="scores">
      {SCORE_KEYS.map((k) => (
        <li key={k}>
          <span className="score-name">{t(`rot.score_${k}`)}</span>
          <span className="score-bar" aria-hidden="true">
            {scores[k] != null && <span style={{ width: `${scores[k]}%` }} className={scores[k] >= 70 ? 'hi' : scores[k] >= 45 ? 'mid' : 'lo'} />}
          </span>
          <span className="score-val">{scores[k] ?? '—'}</span>
        </li>
      ))}
    </ul>
  )
}

export function ConfidencePill({ level }) {
  const { t } = useI18n()
  return <span className={`pill conf conf-${level}`}>{t('rot.confidence')}: {t(`rot.conf_${level}`)}</span>
}

export default function RotationCard({ r, query }) {
  const { t, lang } = useI18n()
  const isCurrent = r.kind === 'current'
  return (
    <article className={`card rot-card ${isCurrent ? 'is-current' : ''}`}>
      <header className="rot-head">
        <span className={`pill ${isCurrent ? '' : 'pill-volt'}`}>{isCurrent ? t('rot.now') : t('rot.suggested')}</span>
        <span className="rot-total" aria-label={t('rot.total')}>{r.total}<span className="tile-unit">/100</span></span>
      </header>
      <h2 className="rot-name">{r.name}</h2>
      <ol className="rot-crops">
        {r.crops.map((c, i) => (
          <li key={i} className={c.cover_crop ? 'is-cover' : ''}>
            <span className="rot-y">{t('rot.yearShort')}{c.year}</span>{lang === 'mk' ? c.name_mk : c.name}
          </li>
        ))}
      </ol>
      <MonthStrip strip={r.strip} crops={r.crops} />
      <ScoreBars scores={r.scores} />
      <p className="rot-why">{r.why}</p>
      <footer className="rot-foot">
        <ConfidencePill level={r.confidence} />
        <Link className="btn" to={`/rotations/${r.id}${query}`}>{t('rot.details')} →</Link>
      </footer>
    </article>
  )
}
