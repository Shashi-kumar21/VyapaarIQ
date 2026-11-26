import { AlertOctagon, ArrowRight, CalendarClock, FilePlus2, Inbox, Wallet } from 'lucide-react'
import { Link } from 'react-router'
import ForecastChart from '../components/ForecastChart.jsx'
import { Card, Empty, ErrorBox, Loading, PageHeader, SeverityChip, Stat, TierBadge } from '../components/ui.jsx'
import { api } from '../lib/api.js'
import { deadlineText } from '../lib/deadline.js'
import { date, inr } from '../lib/format.js'
import { useApi } from '../lib/useApi.js'
import { PHONE, useMediaQuery } from '../lib/useMediaQuery.js'
import { btn } from '../lib/styles.js'

const TIERS = ['High', 'Medium', 'Low']
const TIER_BAR = { High: 'bg-bad', Medium: 'bg-warn', Low: 'bg-ok' }

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
      <section className="space-y-6">
        <PageHeader title="Dashboard" tool="dashboard" />
        <Empty title="No invoices yet" icon={Inbox}
               action={<Link to="/packages/new" className={btn.primary}><FilePlus2 aria-hidden="true" className="size-4" />Upload a package</Link>}>
          Upload the documents for one invoice to see its checks, risk and next actions here.
        </Empty>
      </section>
    )
  }

  // Same population as the forecast totals: leave out suspected duplicates and unverified amounts,
  // so the tier card and "Open receivables" always add up to the same figure.
  const excludedIds = new Set(f30.excluded.map((e) => e.id))
  const counted = open.filter((i) => !excludedIds.has(i.id))
  const byTier = Object.fromEntries(TIERS.map((t) => [t, counted.filter((i) => i.risk_tier === t)]))
  const tierMax = Math.max(1, ...TIERS.map((t) => byTier[t].length))
  const excluded = f30.totals.excluded_count
  const dueOf = Object.fromEntries(invoices.map((i) => [i.id, i.due_date]))

  return (
    <section className="space-y-6">
      <PageHeader title="Dashboard" tool="dashboard"
                  actions={<Link to="/packages/new" className={btn.primary}><FilePlus2 aria-hidden="true" className="size-4" />New package</Link>}>
        Receivables as of {date(f30.as_of)} · {f30.totals.count} open invoice(s)
      </PageHeader>

      <div>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Open receivables" value={inr(f30.totals.open)} hint={`${f30.totals.count} open invoice(s)`}
                icon={Wallet} tool="openReceivables" />
          <Stat label="Cash at risk · 30 days" value={inr(f30.totals.at_risk)} tone="bad" title={f30.formula}
                hint={`not expected by ${date(f30.window_end)}`} icon={AlertOctagon} tool="cashAtRisk" />
          <Stat label="Cash at risk · 60 days" value={inr(f60.totals.at_risk)} tone="warn" title={f60.formula}
                hint={`not expected by ${date(f60.window_end)}`} icon={CalendarClock} tool="cashAtRisk" />
          <Stat label="Expected in 30 days" value={inr(f30.totals.expected_in_window)} tone="ok" title={f30.formula}
                icon={ArrowRight} tool="expected" />
        </div>
        <p className="mt-2 text-xs text-muted">
          <abbr title={f30.formula} className="cursor-help">How is this calculated?</abbr> · {f30.note}
          {excluded > 0 && ` · ${excluded} invoice(s) left out (suspected duplicate or unverified amount).`}
        </p>
      </div>

      <Card title="Open receivables by expected payment" tool="forecast" aside="Illustrative · synthetic demo history">
        <ForecastChart forecast={f30} />
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Invoices by risk tier" tool="tiers" aside="Illustrative">
          <ul className="space-y-3">
            {TIERS.map((t) => (
              <li key={t} className="text-sm">
                <div className="flex items-center justify-between">
                  <TierBadge tier={t} />
                  <span className="tabular-nums">
                    <b>{byTier[t].length}</b> · {inr(byTier[t].reduce((s, i) => s + (i.amount_total || 0), 0))}
                  </span>
                </div>
                <div aria-hidden="true" className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-paper">
                  <div className={`h-full rounded-full ${TIER_BAR[t]}`} style={{ width: `${(100 * byTier[t].length) / tierMax}%` }} />
                </div>
              </li>
            ))}
          </ul>
          {excluded > 0 && (
            <p className="mt-4 text-xs text-muted">
              Excludes {excluded} invoice(s) left out of the forecast, so the totals match Open receivables.
            </p>
          )}
        </Card>

        <Card title="Top actions due" tool="topActions" aside="Ranked by severity, then date" className="lg:col-span-2">
          {actions.length === 0 ? (
            <p className="text-sm text-muted">No open actions. Every check passed.</p>
          ) : (
            <ol className="divide-y divide-line">
              {actions.map((a) => (
                <li key={`${a.invoice_id}-${a.check_id}`} className="flex items-start gap-3 py-3 text-sm first:pt-0 last:pb-0">
                  <SeverityChip severity={a.severity} />
                  <div className="min-w-0 flex-1">
                    <Link to={`/invoices/${a.invoice_id}`} className="font-medium text-ink hover:text-accent hover:underline">{a.title}</Link>
                    <div className="mt-0.5 text-xs text-muted">
                      {a.invoice_no || `Invoice #${a.invoice_id}`} · {a.buyer_name || 'buyer unverified'}
                      {' · '}{deadlineText(a.due_by, dueOf[a.invoice_id])} · {a.check_id}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>

      <Card title="Invoices" tool="readiness" aside={`${invoices.length} on record`}>
        {phone ? (
          <ul className="divide-y divide-line" aria-label="Invoices">
            {invoices.map((i) => (
              <li key={i.id} className="py-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <Link to={`/invoices/${i.id}`} className={`${btn.link} font-mono text-xs`}>
                    {i.invoice_no || `#${i.id}`}
                  </Link>
                  <TierBadge tier={i.risk_tier} />
                </div>
                <div className="truncate text-ink">{i.buyer_name || <span className="text-unsure">unverified</span>}</div>
                <div className="flex flex-wrap gap-x-3 text-xs text-muted">
                  <span>{i.amount_total === null ? <span className="text-unsure">amount to verify</span> : inr(i.amount_total)}</span>
                  <span>due {date(i.due_date)} (est.)</span>
                  <span>score {i.readiness_score ?? '—'}</span>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="-mx-5 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="whitespace-nowrap border-y border-line bg-paper text-left text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="py-2 pl-5 pr-3 font-medium">Invoice</th><th className="pr-3 font-medium">Buyer</th>
                  <th className="pr-3 text-right font-medium">Amount</th>
                  <th className="pr-3 font-medium">Due (est.)</th>
                  <th className="pr-3 text-right font-medium">Score</th><th className="pr-5 font-medium">Tier</th>
                </tr>
              </thead>
              <tbody className="tabular-nums">
                {invoices.map((i) => (
                  <tr key={i.id} className="whitespace-nowrap border-b border-line last:border-0 hover:bg-paper/70">
                    <td className="py-2.5 pl-5 pr-3">
                      <Link to={`/invoices/${i.id}`} className={`${btn.link} font-mono text-xs`}>
                        {i.invoice_no || `#${i.id}`}
                      </Link>
                    </td>
                    <td className="max-w-56 truncate pr-3" title={i.buyer_name || ''}>{i.buyer_name || <span className="text-unsure">unverified</span>}</td>
                    <td className="pr-3 text-right">
                      {i.amount_total === null ? <span className="text-unsure">to verify</span> : inr(i.amount_total)}
                    </td>
                    <td className="pr-3">{date(i.due_date)}</td>
                    <td className="pr-3 text-right">{i.readiness_score ?? '—'}</td>
                    <td className="pr-5"><TierBadge tier={i.risk_tier} /></td>
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
