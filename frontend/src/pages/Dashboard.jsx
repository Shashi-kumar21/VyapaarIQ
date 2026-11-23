import { Link } from 'react-router-dom'
import ForecastChart from '../components/ForecastChart.jsx'
import { Card, Empty, ErrorBox, Loading, SeverityChip, Stat, TierBadge } from '../components/ui.jsx'
import { api } from '../lib/api.js'
import { deadlineText } from '../lib/deadline.js'
import { date, inr } from '../lib/format.js'
import { useApi } from '../lib/useApi.js'
import { PHONE, useMediaQuery } from '../lib/useMediaQuery.js'

const TIERS = ['High', 'Medium', 'Low']

async function loadDashboard() {
  const [invoices, f30, f60, actions] = await Promise.all([
    api.listInvoices(), api.forecast(30), api.forecast(60), api.topActions(5),
  ])
  return { invoices, f30, f60, actions }
}

/** Dashboard (BUILD_SPEC §13.1): open receivables, cash at risk 30/60, tiers, top 5 actions. */
export default function Dashboard() {
  const { data, error, loading, reload } = useApi(loadDashboard)
  const phone = useMediaQuery(PHONE)

  if (loading) return <Loading label="Loading dashboard…" />
  if (error) return <ErrorBox error={error} onRetry={reload} />

  const { invoices, f30, f60, actions } = data
  const open = invoices.filter((i) => i.status === 'open')

  if (invoices.length === 0) {
    return (
      <section>
        <h1 className="text-2xl font-semibold mb-4">Dashboard</h1>
        <Empty title="No invoices yet">
          <Link to="/packages/new" className="text-blue-700 underline">Upload a package</Link> to see
          checks, risk and actions here.
        </Empty>
      </section>
    )
  }

  // Same population as the forecast totals: leave out suspected duplicates and unverified amounts,
  // so the tier card and "Open receivables" always add up to the same figure.
  const excludedIds = new Set(f30.excluded.map((e) => e.id))
  const counted = open.filter((i) => !excludedIds.has(i.id))
  const byTier = Object.fromEntries(TIERS.map((t) => [t, counted.filter((i) => i.risk_tier === t)]))
  const excluded = f30.totals.excluded_count
  const dueOf = Object.fromEntries(invoices.map((i) => [i.id, i.due_date]))

  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Stat label="Open receivables" value={inr(f30.totals.open)} hint={`${f30.totals.count} open invoice(s)`} />
        <Stat label="Cash at risk · 30 days" value={inr(f30.totals.at_risk)} tone="bad" title={f30.formula}
              hint={`not expected by ${date(f30.window_end)}`} />
        <Stat label="Cash at risk · 60 days" value={inr(f60.totals.at_risk)} tone="warn" title={f60.formula}
              hint={`not expected by ${date(f60.window_end)}`} />
        <Stat label="Expected in 30 days" value={inr(f30.totals.expected_in_window)} tone="ok" title={f30.formula} />
      </div>
      <p className="text-xs text-slate-500 -mt-3">
        <abbr title={f30.formula} className="cursor-help">How is this calculated?</abbr> · {f30.note}
        {excluded > 0 && ` · ${excluded} invoice(s) left out (suspected duplicate or unverified amount).`}
      </p>

      <Card title="Open receivables by expected payment" aside="Illustrative · synthetic demo history">
        <ForecastChart forecast={f30} />
      </Card>

      <div className="grid lg:grid-cols-3 gap-4">
        <Card title="Invoices by risk tier" aside="Illustrative">
          <ul className="space-y-2">
            {TIERS.map((t) => (
              <li key={t} className="flex items-center justify-between text-sm">
                <TierBadge tier={t} />
                <span>
                  <b>{byTier[t].length}</b> · {inr(byTier[t].reduce((s, i) => s + (i.amount_total || 0), 0))}
                </span>
              </li>
            ))}
          </ul>
          {excluded > 0 && (
            <p className="text-xs text-slate-500 mt-3">
              Excludes {excluded} invoice(s) left out of the forecast, so the totals match Open receivables.
            </p>
          )}
        </Card>

        <Card title="Top actions due" aside="Ranked by severity, then date" className="lg:col-span-2">
          {actions.length === 0 ? (
            <p className="text-sm text-slate-500">No open actions. Every check passed.</p>
          ) : (
            <ol className="space-y-3">
              {actions.map((a) => (
                <li key={`${a.invoice_id}-${a.check_id}`} className="text-sm flex gap-3 items-start">
                  <SeverityChip severity={a.severity} />
                  <div className="flex-1 min-w-0">
                    <Link to={`/invoices/${a.invoice_id}`} className="font-medium hover:underline">{a.title}</Link>
                    <div className="text-xs text-slate-500">
                      {a.invoice_no || `Invoice #${a.invoice_id}`} · {a.buyer_name || 'buyer unverified'} ·
                      {deadlineText(a.due_by, dueOf[a.invoice_id])} · {a.check_id}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>

      <Card title="Invoices">
        {phone ? (
          <ul className="divide-y divide-slate-100" aria-label="Invoices">
            {invoices.map((i) => (
              <li key={i.id} className="py-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <Link to={`/invoices/${i.id}`} className="text-blue-700 hover:underline font-medium">
                    {i.invoice_no || `#${i.id}`}
                  </Link>
                  <TierBadge tier={i.risk_tier} />
                </div>
                <div className="text-slate-700 truncate">{i.buyer_name || <span className="text-unsure">unverified</span>}</div>
                <div className="text-xs text-slate-500 flex flex-wrap gap-x-3">
                  <span>{i.amount_total === null ? <span className="text-unsure">amount to verify</span> : inr(i.amount_total)}</span>
                  <span>due {date(i.due_date)} (est.)</span>
                  <span>score {i.readiness_score ?? '—'}</span>
                </div>
              </li>
            ))}
          </ul>
        ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-500 border-b border-slate-200 whitespace-nowrap">
              <tr>
                <th className="py-2 pr-3">Invoice</th><th className="pr-3">Buyer</th>
                <th className="pr-3 text-right">Amount</th><th className="pr-3">Due (est.)</th>
                <th className="pr-3 text-right">Score</th><th>Tier</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((i) => (
                <tr key={i.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50 whitespace-nowrap">
                  <td className="py-2 pr-3">
                    <Link to={`/invoices/${i.id}`} className="text-blue-700 hover:underline">
                      {i.invoice_no || `#${i.id}`}
                    </Link>
                  </td>
                  <td className="pr-3 max-w-56 truncate" title={i.buyer_name || ""}>{i.buyer_name || <span className="text-unsure">unverified</span>}</td>
                  <td className="pr-3 text-right">
                    {i.amount_total === null ? <span className="text-unsure">to verify</span> : inr(i.amount_total)}
                  </td>
                  <td className="pr-3">{date(i.due_date)}</td>
                  <td className="pr-3 text-right">{i.readiness_score ?? '—'}</td>
                  <td><TierBadge tier={i.risk_tier} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        )}
      </Card>
    </section>
  )
}
