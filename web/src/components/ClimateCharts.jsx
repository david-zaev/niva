import {
  BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, LineElement, PointElement, Tooltip,
} from 'chart.js'
import { Bar } from 'react-chartjs-2'
import { useI18n } from '../i18n/index.jsx'
import useThemeColors from './useThemeColors.js'

ChartJS.register(BarElement, CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend)

const MONTHS = {
  en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
  mk: ['Јан', 'Фев', 'Мар', 'Апр', 'Мај', 'Јун', 'Јул', 'Авг', 'Сеп', 'Окт', 'Ное', 'Дек'],
}

function doyLabel(doy, lang) {
  const d = new Date(Date.UTC(2001, 0, 1) + (doy - 1) * 86400000)
  return `${d.getUTCDate()} ${MONTHS[lang][d.getUTCMonth()]}`
}

// Shared look: recessive grid and axes, text in text tokens, tooltips on hover
function baseOptions(c, { legend = false, yTitle, yTicks } = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: legend
        ? { position: 'top', align: 'start', labels: { color: c.slate, boxWidth: 10, boxHeight: 10, useBorderRadius: true, borderRadius: 2, font: { family: c['font-body'] } } }
        : { display: false },
      tooltip: {
        backgroundColor: c.ink, titleColor: c.card, bodyColor: c.card, padding: 10, cornerRadius: 8,
        titleFont: { family: c['font-mono'] }, bodyFont: { family: c['font-body'] },
      },
    },
    scales: {
      x: { grid: { display: false }, border: { color: c.line }, ticks: { color: c.smoke, font: { family: c['font-mono'], size: 10 } } },
      y: {
        grid: { color: c.line }, border: { display: false },
        ticks: { color: c.smoke, font: { family: c['font-mono'], size: 10 }, ...(yTicks || {}) },
        title: yTitle ? { display: true, text: yTitle, color: c.smoke, font: { family: c['font-mono'], size: 10 } } : undefined,
      },
    },
  }
}

const bar = { borderRadius: { topLeft: 4, topRight: 4 }, borderSkipped: 'bottom', maxBarThickness: 18 }

export function WaterBalanceChart({ monthly }) {
  const { t, lang } = useI18n()
  const c = useThemeColors()
  const data = {
    labels: MONTHS[lang],
    datasets: [
      { label: t('climate.rain'), data: monthly.map((m) => m.rain_mm), backgroundColor: c['viz-rain'], ...bar },
      { label: t('climate.et0'), data: monthly.map((m) => m.et0_mm), backgroundColor: c['viz-et0'], ...bar },
    ],
  }
  const opts = baseOptions(c, { legend: true, yTitle: 'mm / month' })
  opts.plugins.tooltip.callbacks = {
    footer: (items) => {
      const m = monthly[items[0].dataIndex]
      return `${t('climate.balance')}: ${m.balance_mm > 0 ? '+' : ''}${m.balance_mm} mm`
    },
  }
  opts.datasets = { bar: { categoryPercentage: 0.7, barPercentage: 0.9 } }
  return <div className="chart"><Bar data={data} options={opts} /></div>
}

export function HeatDaysChart({ yearly, baselineAvg }) {
  const { t } = useI18n()
  const c = useThemeColors()
  const data = {
    labels: yearly.map((y) => y.year),
    datasets: [
      { type: 'bar', label: t('climate.heatDays'), data: yearly.map((y) => y.heat_days), backgroundColor: c['viz-heat'], ...bar, maxBarThickness: 10, order: 2 },
      {
        type: 'line', label: t('climate.normalAvg'), data: yearly.map(() => baselineAvg),
        borderColor: c.slate, borderWidth: 2, borderDash: [5, 4], pointRadius: 0, order: 1,
      },
    ],
  }
  const opts = baseOptions(c, { legend: true, yTitle: t('climate.daysUnit') })
  opts.scales.x.ticks.maxTicksLimit = 8
  return <div className="chart"><Bar data={data} options={opts} /></div>
}

export function FrostChart({ yearly }) {
  const { t, lang } = useI18n()
  const c = useThemeColors()
  const rows = yearly.filter((y) => y.last_spring_frost_doy && y.first_autumn_frost_doy)
  const data = {
    labels: rows.map((y) => y.year),
    datasets: [{
      label: t('climate.frostFree'),
      data: rows.map((y) => [y.last_spring_frost_doy, y.first_autumn_frost_doy]),
      backgroundColor: c['viz-frost'], borderRadius: 4, borderSkipped: false, maxBarThickness: 10,
    }],
  }
  const opts = baseOptions(c, { yTicks: { callback: (v) => doyLabel(v, lang), stepSize: 30 } })
  opts.scales.y.min = 60
  opts.scales.y.max = 345
  opts.scales.x.ticks.maxTicksLimit = 8
  opts.plugins.tooltip.callbacks = {
    label: (item) => {
      const [a, b] = item.raw
      return `${t('climate.lastSpring')} ${doyLabel(a, lang)} · ${t('climate.firstAutumn')} ${doyLabel(b, lang)} (${b - a} ${t('climate.daysUnit')})`
    },
  }
  return <div className="chart"><Bar data={data} options={opts} /></div>
}
