// Show / hide details: a quiet button with a chevron that turns when open
export default function Toggle({ open, onClick, more, less }) {
  return (
    <button type="button" className="toggle" aria-expanded={open} onClick={onClick}>
      <span>{open ? less : more}</span>
      <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8"
        strokeLinecap="round" strokeLinejoin="round"><path d="m6 8 4 4 4-4" /></svg>
    </button>
  )
}
