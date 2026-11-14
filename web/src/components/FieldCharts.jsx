import {
  BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, LineElement, PointElement, Tooltip,
} from 'chart.js'
import { Bar, Line } from 'react-chartjs-2'
import { useI18n } from '../i18n/index.jsx'
import { baseOptions } from './ClimateCharts.jsx'
import useThemeColors from './useThemeColors.js'
import { useDay } from './util.js'

ChartJS.register(BarElement, CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend)

const bar = { borderRadius: { topLeft: 4, topRight: 4 }, borderSkipped: 'bottom', maxBarThickness: 14 }
const line = { borderWidth: 2, pointRadius: 0, pointHoverRadius: 5, tension: 0.3 }
const short = { day: 'numeric', month: 'short' }

// NASA POWER GWETTOP / GWETROOT (0-1 -> %) and ERA5-Land top 7 cm (volumetric %), last ~2 months
export function WetnessChart({ daily }) {
  const { t } = useI18n()
  const c = useThemeColors()
  const day = useDay()
  const rows = daily.filter((r) => r.gwettop != null || r.sm != null)
  const data = {
    labels: rows.map((r) => day(r.day, short)),
    datasets: [
      { label: t('metrics.gwettop'), data: rows.map((r) => (r.gwettop == null ? null : Math.round(r.gwettop * 100))), borderColor: c['viz-rain'], backgroundColor: c['viz-rain'], ...line },
      { label: t('metrics.gwetroot'), data: rows.map((r) => (r.gwetroot == null ? null : Math.round(r.gwetroot * 100))), borderColor: c['viz-frost'], backgroundColor: c['viz-frost'], ...line },
      { label: t('metrics.era5'), data: rows.map((r) => r.sm), borderColor: c.smoke, backgroundColor: c.smoke, borderDash: [4, 4], ...line },
    ],
  }
  const opts = baseOptions(c, { legend: true, yTitle: '%' })
  opts.scales.y.min = 0
  opts.scales.y.max = 100
  return <div className="chart"><Line data={data} options={opts} /></div>
}

// Daily rain (bars) against the water the crop uses: ET0 and, when a crop is entered, ETa = ET0 x Kc
export function WaterUseChart({ daily }) {
  const { t } = useI18n()
  const c = useThemeColors()
  const day = useDay()
  const rows = daily.filter((r) => r.rain_mm != null).slice(-30)
  const hasEta = rows.some((r) => r.eta != null)
  const data = {
    labels: rows.map((r) => day(r.day, short)),
    datasets: [
      { type: 'bar', label: t('metrics.rain'), data: rows.map((r) => r.rain_mm), backgroundColor: c['viz-rain'], ...bar, order: 2 },
      { type: 'line', label: 'ET₀', data: rows.map((r) => r.et0), borderColor: c.smoke, backgroundColor: c.smoke, ...line, order: 1 },
      ...(hasEta ? [{ type: 'line', label: t('metrics.eta'), data: rows.map((r) => r.eta), borderColor: c['viz-et0'], backgroundColor: c['viz-et0'], ...line, order: 0 }] : []),
    ],
  }
  return <div className="chart"><Bar data={data} options={baseOptions(c, { legend: true, yTitle: 'mm / day' })} /></div>
}

// MODIS NDVI at the field pixel, each year its own line, so this season reads against the ones before
export function NdviChart({ points }) {
  const { lang } = useI18n()
  const c = useThemeColors()
  const years = [...new Set(points.map((p) => p.day.slice(0, 4)))].slice(-3)
  const colors = [c.ash, c.smoke, c.ink]
  const months = Array.from({ length: 12 }, (_, i) => new Intl.DateTimeFormat(lang === 'mk' ? 'mk-MK' : 'en-GB', { month: 'short' }).format(new Date(2001, i, 15)))
  const doy = (iso) => Math.round((Date.parse(`${iso}T12:00:00Z`) - Date.parse(`${iso.slice(0, 4)}-01-01T12:00:00Z`)) / 86400000) + 1
  const data = {
    datasets: years.map((y, i) => ({
      label: y, data: points.filter((p) => p.day.startsWith(y)).map((p) => ({ x: doy(p.day), y: p.ndvi })),
      borderColor: colors[i + 3 - years.length], backgroundColor: colors[i + 3 - years.length], ...line, pointRadius: 2,
      borderWidth: i === years.length - 1 ? 2.5 : 1.5,
    })),
  }
  const opts = baseOptions(c, { legend: true, yTitle: 'NDVI' })
  opts.scales.x = { ...opts.scales.x, type: 'linear', min: 1, max: 366,
    ticks: { ...opts.scales.x.ticks, stepSize: 30.5, callback: (v) => months[Math.min(11, Math.floor((v - 1) / 30.5))] } }
  opts.scales.y.min = 0
  opts.scales.y.max = 1
  opts.plugins.tooltip.callbacks = { title: (items) => `${items[0].dataset.label} · ${months[Math.min(11, Math.floor((items[0].parsed.x - 1) / 30.5))]}` }
  return <div className="chart"><Line data={data} options={opts} /></div>
}

// MakStat production in the region, tonnes per year
export function ProductionChart({ series }) {
  const { t } = useI18n()
  const c = useThemeColors()
  const rows = series.filter((r) => r.production_t != null)
  const data = {
    labels: rows.map((r) => r.year),
    datasets: [{ label: t('market.produced'), data: rows.map((r) => r.production_t), backgroundColor: c['viz-frost'], ...bar }],
  }
  return <div className="chart chart-small"><Bar data={data} options={baseOptions(c, { yTitle: 't' })} /></div>
}

// The farmer's own yields (kg/ha) by year, next to the official municipality average
export function YieldChart({ points, official }) {
  const { t } = useI18n()
  const c = useThemeColors()
  const data = {
    labels: points.map((p) => p.label),
    datasets: [
      { type: 'bar', label: t('crops.yourYield'), data: points.map((p) => p.kgHa), backgroundColor: c['viz-rain'], ...bar },
      ...(official ? [{ type: 'line', label: t('crops.officialYield'), data: points.map(() => official), borderColor: c.smoke, borderDash: [5, 4], ...line }] : []),
    ],
  }
  return <div className="chart chart-small"><Bar data={data} options={baseOptions(c, { legend: true, yTitle: 'kg/ha' })} /></div>
}
