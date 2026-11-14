import { Chart as ChartJS, Filler } from 'chart.js'
import { Line } from 'react-chartjs-2'
import { useI18n } from '../i18n/index.jsx'
import { baseOptions } from './ClimateCharts.jsx'
import useThemeColors from './useThemeColors.js'

ChartJS.register(Filler)

// 7-day soil moisture: the model's line inside its error band, with this place's "dry" level dashed
export default function ForecastChart({ fc }) {
  const { t, lang } = useI18n()
  const c = useThemeColors()
  const fmt = new Intl.DateTimeFormat(lang === 'mk' ? 'mk-MK' : 'en-GB', { weekday: 'short', day: 'numeric' })
  const labels = fc.days.map((d, i) => (i === 0 ? t('fc.today') : fmt.format(new Date(`${d.day}T12:00:00`))))
  const band = `${c['viz-rain']}33`
  const data = {
    labels,
    datasets: [
      { label: t('fc.bandHigh'), data: fc.days.map((d) => d.high), borderWidth: 0, pointRadius: 0, fill: '+1', backgroundColor: band },
      { label: t('fc.bandLow'), data: fc.days.map((d) => d.low), borderWidth: 0, pointRadius: 0, fill: false },
      {
        label: t('fc.forecast'), data: fc.days.map((d) => d.soil_moisture), borderColor: c['viz-rain'], backgroundColor: c['viz-rain'],
        borderWidth: 2, pointRadius: 4, pointHoverRadius: 6, pointBorderColor: c.card, pointBorderWidth: 2, tension: 0.3,
      },
      {
        label: t('fc.dryLine'), data: fc.days.map(() => fc.dry_threshold), borderColor: c.wait, borderDash: [5, 4],
        borderWidth: 1.5, pointRadius: 0, fill: false,
      },
    ],
  }
  const opts = baseOptions(c, { yTitle: t('fc.unit') })
  const values = fc.days.flatMap((d) => [d.low, d.high]).concat(fc.dry_threshold)
  opts.scales.y.suggestedMin = Math.max(0, Math.floor(Math.min(...values) - 3))
  opts.scales.y.suggestedMax = Math.ceil(Math.max(...values) + 3)
  opts.plugins.tooltip.filter = (item) => item.datasetIndex === 2 || item.datasetIndex === 3
  opts.plugins.tooltip.callbacks = {
    label: (item) => `${item.dataset.label}: ${item.parsed.y.toFixed(1)}%`,
    footer: (items) => {
      const d = fc.days[items[0].dataIndex]
      return `${t('fc.range')}: ${d.low}–${d.high}%`
    },
  }
  return <div className="chart"><Line data={data} options={opts} /></div>
}
