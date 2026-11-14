import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fieldId, ownerToken, pairDevice } from '../api.js'
import { save, useI18n } from '../i18n/index.jsx'

// The QR sticker on a sensor opens /pair?d=<device id>&c=<pair code>. A phone that owns a field pairs at once;
// otherwise the code is kept and used when the farmer finishes setting up their field.
export default function Pair() {
  const { t } = useI18n()
  const [params] = useSearchParams()
  const d = (params.get('d') ?? '').trim().toUpperCase()
  const c = (params.get('c') ?? '').trim().toUpperCase()
  const id = fieldId()
  const owner = ownerToken(id)
  const [state, setState] = useState(d && c ? (owner ? 'pairing' : 'needField') : 'bad')

  useEffect(() => {
    if (state === 'needField') save('niva.pendingPair', JSON.stringify({ d, c }))
    if (state !== 'pairing') return
    pairDevice(id, d, c).then(() => setState('done')).catch((e) => setState(e.status === 404 ? 'wrong' : 'failed'))
  }, [state]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className="screen">
      <header className="screen-head">
        <span className="pill">{d || '—'}</span>
        <h1>{t('pair.title')}</h1>
      </header>
      <div className="card">
        <p>{t(`pair.${state}`)}</p>
        {state === 'needField' && <Link className="btn btn-volt" to="/setup">{t('pair.setUp')} →</Link>}
        {state === 'done' && <Link className="btn" to="/">{t('pair.see')} →</Link>}
        {['wrong', 'failed', 'bad'].includes(state) && <Link className="btn" to="/more">{t('pair.manual')} →</Link>}
      </div>
    </section>
  )
}
