// The Niva wordmark from brand/logo/banner-latin-2.svg without its green tile: yellow pin + NIVA letters.
// Letters use currentColor (ink in light and dark); in light mode the pin gets an ink edge so yellow reads on white.
export default function Logo({ height = 30 }) {
  return (
    <svg className="logo" viewBox="146 64 508 150" height={height} role="img" aria-label="Niva">
      <path className="logo-pin" fillRule="evenodd" d="M210.34 70.89C173.45 70.89 152.34 98.32 152.34 128.89C152.34 165.78 210.34 208.00 210.34 208.00C210.34 208.00 268.34 165.78 268.34 128.89C268.34 98.32 247.23 70.89 210.34 70.89ZM210.34 104.53a24.36 24.36 0 1 0 0 48.72a24.36 24.36 0 1 0 0 -48.72Z" />
      <g fill="currentColor">
        <g transform="translate(303.14 92.00) scale(116.00)">
          <path d="M0.00 0.00L0.21 0.00L0.21 1.00L0.00 1.00Z" /><path d="M0.59 0.00L0.80 0.00L0.80 1.00L0.59 1.00Z" /><path d="M0.00 0.00L0.25 0.00L0.80 1.00L0.55 1.00Z" />
        </g>
        <g transform="translate(411.02 92.00) scale(116.00)"><path d="M0.00 0.00L0.21 0.00L0.21 1.00L0.00 1.00Z" /></g>
        <g transform="translate(446.98 92.00) scale(116.00)"><path d="M0.00 0.00L0.23 0.00L0.45 0.64L0.67 0.00L0.90 0.00L0.57 1.00L0.34 1.00Z" /></g>
        <g transform="translate(543.26 92.00) scale(116.00)">
          <path d="M0.00 1.00L0.34 0.00L0.57 0.00L0.90 1.00L0.67 1.00L0.45 0.36L0.23 1.00Z" /><path d="M0.20 0.60L0.70 0.60L0.70 0.78L0.20 0.78Z" />
        </g>
      </g>
    </svg>
  )
}
