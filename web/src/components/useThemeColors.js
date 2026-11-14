import { useEffect, useState } from 'react'

// Reads the CSS colour tokens so charts (canvas) follow the light/dark theme.
const names = ['ink', 'slate', 'smoke', 'line', 'card', 'viz-rain', 'viz-et0', 'viz-heat', 'viz-frost', 'font-body', 'font-mono']

function read() {
  const cs = getComputedStyle(document.documentElement)
  return Object.fromEntries(names.map((n) => [n, cs.getPropertyValue(`--${n}`).trim()]))
}

export default function useThemeColors() {
  const [colors, setColors] = useState(read)
  useEffect(() => {
    const update = () => setColors(read())
    const obs = new MutationObserver(update)
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    media.addEventListener('change', update)
    return () => {
      obs.disconnect()
      media.removeEventListener('change', update)
    }
  }, [])
  return colors
}
