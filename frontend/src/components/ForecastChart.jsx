import { useState } from 'react'
import { inr } from '../lib/format.js'

// Cash-at-risk forecast chart (BUILD_SPEC §9, task T4.11).
// Form: one series of amounts over ordered buckets -> horizontal bars in their natural order,
// one hue, no legend (the title names the series). Bars <= 24px with a 4px rounded data-end
// and a square baseline, value at the tip in text ink, a hairline baseline, a hover/focus
// tooltip per bar, and a table view for every number (dataviz method; colour validated:
// #2a78d6 on the white card passes all checks).

const BUCKET_LABEL = {
  overdue: 'Overdue (expected date passed)',
  next_30: 'Next 30 days',
  days_31_60: '31–60 days',
  beyond_60: 'Beyond 60 days',
  unknown: 'Due date unknown',
}
const BAR = '#2a78d6'
const ROW = 34
const BAR_H = 20
const LABEL_W = 210
const W = 1000 // ~1:1 with the dashboard card on desktop, so 12px text stays 12-13px
const VALUE_W = 110

/** Round-ended bar from x=0 (square at the baseline, 4px radius at the data end). */
function barPath(x0, y, w, h, r = 4) {
  const rr = Math.min(r, w / 2, h / 2)
  if (w <= 0) return ''
  return `M${x0},${y} h${w - rr} a${rr},${rr} 0 0 1 ${rr},${rr} v${h - 2 * rr} a${rr},${rr} 0 0 1 ${-rr},${rr} h${-(w - rr)} z`
}

export default function ForecastChart({ forecast }) {
  const [hover, setHover] = useState(null)
  // On a phone the 1000-unit chart scales its text below 7px, so the table is the default view there.
  const [table, setTable] = useState(() => {
    try { return window.matchMedia('(max-width: 639px)').matches } catch { return false }
  })
  const buckets = forecast.buckets.filter((b) => BUCKET_LABEL[b.key])
  const max = Math.max(...buckets.map((b) => b.amount), 0)
  const open = forecast.totals.open || 0
  const plotW = W - LABEL_W - VALUE_W
  const H = buckets.length * ROW + 8

  if (open === 0) return <p className="text-sm text-slate-500">No open receivables to forecast.</p>

  return (
    <div>
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[480px] h-auto" role="img"
             aria-label={`Open receivables by expected payment bucket, as of ${forecast.as_of}`}>
          <line x1={LABEL_W} y1={4} x2={LABEL_W} y2={H - 4} stroke="#e2e8f0" strokeWidth="1" />
          {buckets.map((b, i) => {
            const y = 4 + i * ROW + (ROW - BAR_H) / 2
            const w = max ? (b.amount / max) * plotW : 0
            const share = open ? Math.round((100 * b.amount) / open) : 0
            const tip = `${BUCKET_LABEL[b.key]}: ${inr(b.amount)} (${share}% of open receivables)`
            return (
              <g key={b.key} data-bucket={b.key} tabIndex={0} aria-label={tip}
                 onMouseEnter={() => setHover({ i, tip })} onMouseLeave={() => setHover(null)}
                 onFocus={() => setHover({ i, tip })} onBlur={() => setHover(null)} className="focus:outline-none">
                {/* hit target: the whole row, bigger than the mark */}
                <rect x={0} y={4 + i * ROW} width={W} height={ROW} fill={hover?.i === i ? '#f1f5f9' : 'transparent'} />
                <text x={LABEL_W - 10} y={y + BAR_H / 2 + 4} textAnchor="end" fontSize="12" fill="#475569">
                  {BUCKET_LABEL[b.key]}
                </text>
                {w > 0 && <path d={barPath(LABEL_W, y, Math.max(w, 2), BAR_H)} fill={BAR} />}
                <text x={LABEL_W + Math.max(w, 0) + 6} y={y + BAR_H / 2 + 4} fontSize="12" fill="#0f172a"
                      style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {inr(b.amount)}
                </text>
              </g>
            )
          })}
        </svg>
      </div>
      <div className="min-h-5 text-xs text-slate-700" aria-live="polite">{hover ? hover.tip : ' '}</div>
      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 mt-1">
        <abbr title={forecast.formula} className="cursor-help">How is this calculated?</abbr>
        <span>As of {forecast.as_of} · buckets by expected payment date</span>
        <button type="button" onClick={() => setTable((t) => !t)} className="underline">
          {table ? 'Hide table' : 'Show as table'}
        </button>
      </div>
      {table && (
        <table className="text-sm mt-2">
          <thead className="text-xs text-slate-500 text-left">
            <tr><th className="pr-6 py-1">Bucket</th><th className="pr-6 text-right">Amount</th><th className="text-right">Share</th></tr>
          </thead>
          <tbody style={{ fontVariantNumeric: 'tabular-nums' }}>
            {buckets.map((b) => (
              <tr key={b.key}>
                <td className="pr-6 py-0.5">{BUCKET_LABEL[b.key]}</td>
                <td className="pr-6 text-right">{inr(b.amount)}</td>
                <td className="text-right">{open ? Math.round((100 * b.amount) / open) : 0}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
