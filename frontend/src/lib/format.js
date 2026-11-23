// Display helpers. Amounts arrive as plain INR numbers from the API (docs/api_contract.md).

/**
 * Round half to even, like Python's format() used by the backend (app/fmt.py), so the UI
 * and the dispute pack never disagree by a rupee: 22922.5 -> 22922, 22923.5 -> 22924.
 */
export function roundHalfEven(x, digits = 0) {
  const sign = x < 0 ? -1 : 1
  const a = Math.abs(x)
  // toFixed() rounds the exact binary value correctly but sends exact ties up. Find ties on the
  // exact decimal expansion: 2.675 is really 2.67499… (-> 2.67, like Python), whereas 0.125 and
  // 22922.5 are exact ties (-> even). Multiplying by 10^digits first would hide this.
  const [, frac = ''] = a.toFixed(20).split('.')
  const tie = /^50*$/.test(frac.slice(digits))
  const up = Number(a.toFixed(digits)) // nearest; the larger one on an exact tie
  if (!tie) return sign * up
  const lastDigit = Math.round(up * 10 ** digits) % 10
  return sign * (lastDigit % 2 === 0 ? up : up - 10 ** -digits)
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
