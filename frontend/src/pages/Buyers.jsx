import { Card, Empty, ErrorBox, Loading } from '../components/ui.jsx'
import { api } from '../lib/api.js'
import { useApi } from '../lib/useApi.js'

// Buyers (BUILD_SPEC §8 and §13.4, task T3.14): reliability from the supplier's own history.
// Labels carry an icon + text, never colour alone; history is labelled synthetic demo data.

const LABEL_STYLE = {
  Reliable: { icon: '✓', cls: 'bg-green-100 text-green-800' },
  Mixed: { icon: '~', cls: 'bg-amber-100 text-amber-900' },
  Slow: { icon: '!', cls: 'bg-red-100 text-red-800' },
  'Insufficient history': { icon: '–', cls: 'bg-slate-100 text-slate-600' },
}
const TREND = { worsening: '↗ worsening', improving: '↘ improving', stable: '→ stable' }

function num(x, suffix = '') {
  return x === null || x === undefined ? '—' : `${x}${suffix}`
}

export function LabelChip({ label }) {
  const s = LABEL_STYLE[label] || LABEL_STYLE['Insufficient history']
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${s.cls}`}>
      <span aria-hidden="true">{s.icon}</span>{label}
    </span>
  )
}

export default function Buyers() {
  const { data, error, loading, reload } = useApi(() => api.listBuyers())

  if (loading) return <Loading label="Loading buyers…" />
  if (error) return <ErrorBox error={error} onRetry={reload} />

  const anySynthetic = data.some((b) => b.synthetic)
  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-semibold">Buyers</h1>
      <p className="text-sm text-slate-600 max-w-3xl">
        How each buyer has paid <b>this supplier</b> in the past: days late against the due date. It is not
        a credit rating and does not predict whether a buyer will pay. A buyer needs at least 5 paid
        invoices for a label.
      </p>
      {anySynthetic && (
        <p role="note" className="text-sm bg-amber-50 text-amber-900 rounded-lg px-3 py-2">
          Payment history marked “synthetic” is seeded demo data, not real payments.
        </p>
      )}

      {data.length === 0 ? (
        <Empty title="No buyers yet">
          Buyers appear after a package is processed, or run <code>python -m app.seed</code> for demo history.
        </Empty>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase text-slate-500 border-b border-slate-200 whitespace-nowrap">
                <tr>
                  <th className="py-2 pr-3">Buyer</th><th className="pr-3">Reliability</th>
                  <th className="pr-3 text-right">Invoices</th><th className="pr-3 text-right">Median days late</th>
                  <th className="pr-3 text-right">Paid late</th><th className="pr-3 text-right">&gt; 30 days late</th>
                  <th className="pr-3">Trend</th>
                </tr>
              </thead>
              <tbody style={{ fontVariantNumeric: 'tabular-nums' }}>
                {data.map((b) => {
                  const p = b.profile
                  return (
                    <tr key={b.id} className="border-b border-slate-100 last:border-0 align-top" data-buyer={b.id}>
                      <td className="py-2 pr-3">
                        <div className="font-medium">{b.name}</div>
                        <div className="text-xs text-slate-500">
                          {b.gstin || 'GSTIN not recorded'}
                          {b.synthetic && <span className="ml-2 px-1.5 rounded bg-slate-100 text-slate-600">synthetic</span>}
                        </div>
                      </td>
                      <td className="pr-3 py-2"><LabelChip label={p.label} /></td>
                      <td className="pr-3 py-2 text-right">{p.invoices_considered}</td>
                      <td className="pr-3 py-2 text-right">{num(p.median_days_late)}</td>
                      <td className="pr-3 py-2 text-right">{num(p.pct_paid_late, '%')}</td>
                      <td className="pr-3 py-2 text-right">{num(p.pct_paid_over_30_late, '%')}</td>
                      <td className="pr-3 py-2 whitespace-nowrap" title={p.trend_detail || ''}>
                        {p.trend ? TREND[p.trend] || p.trend : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-slate-500 mt-3">{data[0]?.profile?.note}</p>
        </Card>
      )}
    </section>
  )
}
