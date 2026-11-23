// Display helpers. Amounts arrive as plain INR numbers from the API (docs/api_contract.md).

/**
 * Round half to even, like Python's format() used by the backend (app/fmt.py), so the UI
 * and the dispute pack never disagree by a rupee: 22922.5 -> 22922, 22923.5 -> 22924.
 */
export function roundHalfEven(x, digits = 0) {
  const f = 10 ** digits
  const scaled = x * f
  const floor = Math.floor(scaled)
  const diff = scaled - floor
  if (Math.abs(diff - 0.5) < 1e-9) return (floor % 2 === 0 ? floor : floor + 1) / f
  return Math.round(scaled) / f
}

/** Indian digit grouping, whole rupees: 240000 -> "₹2,40,000"; null -> "—". */
export function inr(value, { paise = false } = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  const n = Number(value)
  const digits = paise ? 2 : 0
  const text = roundHalfEven(Math.abs(n), digits).toFixed(digits)
  const [whole, frac] = text.split('.')
  let grouped = whole
  if (whole.length > 3) {
    const head = whole.slice(0, -3)
    const tail = whole.slice(-3)
    grouped = head.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' + tail
  }
  return `${n < 0 ? '-' : ''}₹${grouped}${frac ? '.' + frac : ''}`
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** ISO "2026-10-13" -> "13 Oct 2026"; anything else -> "—". Parsed without time zones. */
export function date(iso) {
  const m = typeof iso === 'string' && /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!m) return '—'
  return `${m[3]} ${MONTHS[Number(m[2]) - 1]} ${m[1]}`
}

/** 0.84 -> "84%"; null -> "—". */
export function pct(fraction) {
  if (fraction === null || fraction === undefined) return '—'
  return `${Math.round(Number(fraction) * 100)}%`
}
