import { useEffect, useState } from 'react'
import { getBuyers, getPrices } from '../api.js'
import { useI18n } from '../i18n/index.jsx'

// "Where to sell" for each crop of a rotation: the ZPIS price (local if this region has one) and verified buyers.
// Buyers only appear once checked against the Ministry register; until then we say so instead of guessing.
export default function SellCard({ crops, region }) {
  const { t, lang } = useI18n()
  const [prices, setPrices] = useState(null)
  const [buyers, setBuyers] = useState([])
  useEffect(() => {
    getPrices().then(setPrices).catch(() => setPrices({ prices: [] }))
    getBuyers().then((d) => setBuyers(d.buyers ?? [])).catch(() => {})
  }, [])
  const seen = new Set()
  const list = crops.filter((c) => !c.cover_crop && !seen.has(c.crop) && seen.add(c.crop))
  return (
    <div className="card sell">
      <h2>{t('sell.title')}</h2>
      <ul className="sell-list">
        {list.map((c) => {
          const p = prices?.prices.find((x) => x.crop === c.crop)
          const local = p?.local?.[region]
          const own = buyers.filter((b) => b.crops?.includes(c.crop))
          return (
            <li key={c.crop}>
              <span className="sell-crop">{lang === 'mk' ? c.name_mk : c.name}</span>
              {p ? (
                <span className="sell-price">
                  <strong>{(local ?? p.price).toFixed(2)}</strong> MKD/kg
                  <span className="muted small"> · {t(`sell.${p.market}`)}{local != null ? ` · ${t('sell.local')}` : ` · ${t('sell.national')}`}</span>
                </span>
              ) : prices ? <span className="muted">{t('sell.noPrice')}</span> : null}
              {own.length > 0 && (
                <span className="sell-buyers">{own.map((b) => b.name).join(' · ')}</span>
              )}
            </li>
          )
        })}
      </ul>
      {buyers.length === 0 && <p className="muted small">{t('sell.noBuyers')}</p>}
      {prices?.retrieved && (
        <p className="source">ZPIS, zpis.gov.mk ({t('sell.retrieved')} {prices.retrieved}) · {t('sell.priceNote')}</p>
      )}
    </div>
  )
}
