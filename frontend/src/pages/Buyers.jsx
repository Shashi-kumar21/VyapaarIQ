import { Users } from 'lucide-react'
import { Card, Empty, ErrorBox, Loading, PageHeader } from '../components/ui.jsx'
import { api } from '../lib/api.js'
import { useApi } from '../lib/useApi.js'

// Buyers (BUILD_SPEC §8 and §13.4, task T3.14): reliability from the supplier's own history.
// Labels carry an icon + text, never colour alone; history is labelled synthetic demo data.

const LABEL_STYLE = {
  Reliable: { icon: '✓', cls: 'bg-green-50 text-green-800 ring-green-600/20' },
  Mixed: { icon: '~', cls: 'bg-amber-50 text-amber-900 ring-amber-600/20' },
  Slow: { icon: '!', cls: 'bg-red-50 text-red-800 ring-red-600/20' },
  'Insufficient history': { icon: '–', cls: 'bg-paper text-muted ring-line' },
}
// U+FE0E asks for the text glyph: without it Windows draws some arrows as colour emoji (B-9).
const TREND = { worsening: '\u2197\uFE0E worsening', improving: '\u2198\uFE0E improving', stable: '\u2192\uFE0E stable' }

function num(x, suffix = '') {
  return x === null || x === undefined ? '—' : `${x}${suffix}`
}

export function LabelChip({ label }) {
  const s = LABEL_STYLE[label] || LABEL_STYLE['Insufficient history']
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${s.cls}`}>
      <span aria-hidden="true">{s.icon}</span>{label}
    </span>
  )
}

export default function Buyers() {
  const { data: res, error, loading, reload } = useApi(async () => {
    const [buyers, health] = await Promise.all([api.listBuyers(), api.health()])
    return { buyers, minHistory: health.min_history }
  })

  if (loading) return <Loading label="Loading buyers…" />
  if (error) return <ErrorBox error={error} onRetry={reload} />

  const data = res.buyers
  const anySynthetic = data.some((b) => b.synthetic)
  return (
    <section className="space-y-5">
      <PageHeader title="Buyers" tool="buyers">
        How each buyer has paid <b className="text-ink">this supplier</b> in the past: days late against the due date. It is not
        a credit rating and does not predict whether a buyer will pay. A buyer needs enough paid
        {res.minHistory ? ` invoices for a label (minimum ${res.minHistory}, from the rule config).` : ' invoices for a label.'}
      </PageHeader>
      {anySynthetic && (
        <p role="note" className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-900">
          Payment history marked “synthetic” is seeded demo data, not real payments.
        </p>
      )}

      {data.length === 0 ? (
        <Empty title="No buyers yet" icon={Users}>
          Buyers appear after a package is processed, or run <code>python -m app.seed</code> for demo history.
        </Empty>
      ) : (
        <Card>
          <div className="-mx-5 -mt-5 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="whitespace-nowrap border-b border-line bg-paper text-left text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="py-2.5 pl-5 pr-3 font-medium">Buyer</th><th className="pr-3 font-medium">Reliability</th>
                  <th className="pr-3 text-right font-medium">Invoices</th><th className="pr-3 text-right font-medium">Median days late</th>
                  <th className="pr-3 text-right font-medium">Paid late</th><th className="pr-3 text-right font-medium">&gt; 30 days late</th>
                  <th className="pr-5 font-medium">Trend</th>
                </tr>
              </thead>
              <tbody style={{ fontVariantNumeric: 'tabular-nums' }}>
                {data.map((b) => {
                  const p = b.profile
                  return (
                    <tr key={b.id} className="border-b border-line align-top last:border-0 hover:bg-paper/70" data-buyer={b.id}>
                      <td className="py-2.5 pl-5 pr-3">
                        <div className="font-medium text-ink">{b.name}</div>
                        <div className="font-mono text-xs text-muted">
                          {b.gstin || 'GSTIN not recorded'}
                          {b.synthetic && <span className="ml-2 rounded bg-paper px-1.5 font-sans text-muted ring-1 ring-inset ring-line">synthetic</span>}
                        </div>
                      </td>
                      <td className="pr-3 py-2"><LabelChip label={p.label} /></td>
                      <td className="pr-3 py-2 text-right">{p.invoices_considered}</td>
                      <td className="pr-3 py-2 text-right">{num(p.median_days_late)}</td>
                      <td className="pr-3 py-2 text-right">{num(p.pct_paid_late, '%')}</td>
                      <td className="pr-3 py-2 text-right">{num(p.pct_paid_over_30_late, '%')}</td>
                      <td className="whitespace-nowrap py-2 pr-5" title={p.trend_detail || ''}>
                        {p.trend ? TREND[p.trend] || p.trend : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-xs text-muted">{data[0]?.profile?.note}</p>
        </Card>
      )}
    </section>
  )
}
