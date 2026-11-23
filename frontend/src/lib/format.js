// Display helpers. Amounts arrive as plain INR numbers from the API (docs/api_contract.md).

/** Indian digit grouping, whole rupees: 240000 -> "₹2,40,000"; null -> "—". */
export function inr(value, { paise = false } = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  const n = Number(value)
  const text = Math.abs(n).toFixed(paise ? 2 : 0)
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
