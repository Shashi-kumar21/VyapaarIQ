import { useState } from 'react'
import { Link, useParams } from 'react-router'
import DisputePackPanel from '../components/DisputePackPanel.jsx'
import DocumentFields from '../components/DocumentFields.jsx'
import EvidenceGraph from '../components/EvidenceGraph.jsx'
import FollowupsPanel from '../components/FollowupsPanel.jsx'
import { Card, ErrorBox, Loading, SeverityChip, TierBadge } from '../components/ui.jsx'
import { api } from '../lib/api.js'
import { date, inr } from '../lib/format.js'
import { useApi } from '../lib/useApi.js'

// Invoice detail (BUILD_SPEC §13.3, tasks T2.13–T2.15, T3.12): the demo screen.

const STATUS_STYLE = {
  pass: 'bg-green-100 text-green-800',
  fail: 'bg-red-100 text-red-800',
  missing: 'bg-red-100 text-red-800',
  uncertain: 'bg-amber-100 text-amber-900',
  skipped: 'bg-slate-100 text-slate-600',
}
const SEV_ORDER = { blocker: 0, warning: 1, info: 2 }
const BASIS = { grn: 'GRN date', challan_received: 'challan received date', deemed: 'deemed acceptance', unknown: 'unknown' }
const TABS = [
  ['checks', 'Checks'], ['actions', 'Actions & score'], ['documents', 'Documents'],
  ['followups', 'Follow-ups'], ['pack', 'Dispute pack'],
]

async function load(id) {
  const [invoice, health] = await Promise.all([api.getInvoice(id), api.health()])
  return { invoice, threshold: health.uncertain_below ?? 0.6 }
}

/** "missing" on an info check means the check was skipped (e.g. C06/C07 with no challan). */
function shownStatus(c) {
  return c.status === 'missing' && c.severity === 'info' ? 'skipped' : c.status
}

function StatusChip({ status }) {
  return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLE[status] || ''}`}>{status}</span>
}

function Header({ inv, a }) {
  const due = a.due
  const interest = a.interest
  return (
    <Card>
      <div className="flex flex-wrap items-start gap-x-8 gap-y-3">
        <div className="min-w-0">
          <div className="text-xs text-slate-500">Invoice</div>
          <h1 className="text-2xl font-semibold">{inv.invoice_no || <span className="text-unsure">No. to verify</span>}</h1>
          <div className="text-sm text-slate-600">
            {inv.buyer_name || <span className="text-unsure">buyer unverified</span>} · dated {date(inv.invoice_date)}
          </div>
        </div>
        <div>
          <div className="text-xs text-slate-500">Amount</div>
          <div className="text-xl font-semibold">
            {inv.amount_total === null ? <span className="text-unsure">to be verified</span> : inr(inv.amount_total)}
          </div>
        </div>
        <div>
          <div className="text-xs text-slate-500">Due date (estimated)</div>
          <div className="text-xl font-semibold">{date(due.due_date)}</div>
          <div className="text-xs text-slate-500">
            from {BASIS[due.acceptance_basis] || due.acceptance_basis}
            {due.acceptance_basis === 'deemed' && <span className="ml-1 text-unsure font-medium">· verify</span>}
            {due.uncertain && <span className="ml-1 text-unsure font-medium">· uncertain</span>}
          </div>
        </div>
        <div>
          <div className="text-xs text-slate-500">Readiness</div>
          <div className="flex items-center gap-2">
            <span className="text-xl font-semibold">{a.score.score}</span><TierBadge tier={a.score.tier} />
          </div>
          <div className="text-xs text-slate-500">Illustrative</div>
        </div>
        <div className="ml-auto flex flex-wrap gap-2 text-xs">
          <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">extractor: {a.extractor_used || '—'}</span>
          {a.fallback_used && <span className="px-2 py-0.5 rounded-full bg-purple-100 text-purple-800">demo fallback</span>}
          {inv.processing_ms != null && (
            <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-700" title="Time to extract and analyse this package">
              processed in {inv.processing_ms < 1000 ? `${inv.processing_ms} ms` : `${(inv.processing_ms / 1000).toFixed(1)} s`}
            </span>
          )}
        </div>
      </div>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-slate-600">How the due date and interest were worked out</summary>
        <p className="mt-2">{due.reasoning}</p>
        {interest && (
          <p className="mt-2">
            {interest.computable
              ? <>Estimated statutory interest: <b>{inr(interest.interest)}</b> ({interest.days_late} day(s) late as of {date(interest.as_of)}, {interest.annual_rate_pct}% a year). <span className="text-slate-500">{interest.formula}</span></>
              : <span className="text-slate-600">{interest.formula}</span>}
          </p>
        )}
        <p className="mt-1 text-xs text-slate-500">{interest?.note || 'Estimated; not legal advice. Verify before use.'}</p>
      </details>
    </Card>
  )
}

const rank = (c) => ({ pass: 2, skipped: 1 }[shownStatus(c)] ?? 0)

function Checks({ checks }) {
  const sorted = [...checks].sort((x, y) =>
    rank(x) - rank(y) || SEV_ORDER[x.severity] - SEV_ORDER[y.severity]
    || x.check_id.localeCompare(y.check_id))
  const open = sorted.filter((c) => !['pass', 'skipped'].includes(shownStatus(c))).length
  return (
    <div>
      <p className="text-sm text-slate-600 mb-2">{open} of {checks.length} checks need attention.</p>
      <ul className="divide-y divide-slate-100">
        {sorted.map((c) => (
          <li key={c.check_id} className="py-2 text-sm flex gap-3 items-start" data-check={c.check_id}>
            <span className="w-9 text-slate-500 font-mono text-xs pt-0.5">{c.check_id}</span>
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{c.name}</span>
                <StatusChip status={shownStatus(c)} />
                {!['pass', 'skipped'].includes(shownStatus(c)) && <SeverityChip severity={c.severity} />}
              </div>
              <p className={['pass', 'skipped'].includes(shownStatus(c)) ? 'text-slate-500' : 'text-slate-700'}>{c.detail}</p>
              {c.explanation && <p className="text-slate-600 italic mt-0.5">{c.explanation}</p>}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function ActionsAndScore({ a }) {
  return (
    <div className="grid lg:grid-cols-3 gap-4">
      <div className="lg:col-span-2">
        <h3 className="font-semibold mb-2">Recommended actions</h3>
        {a.actions.length === 0 ? (
          <p className="text-sm text-slate-500">Nothing to do. Every check passed.</p>
        ) : (
          <ol className="space-y-3">
            {a.actions.map((x) => (
              <li key={`${x.check_id}-${x.priority}`} className="text-sm flex gap-3">
                <span className="w-6 h-6 rounded-full bg-slate-900 text-white text-xs flex items-center justify-center shrink-0">
                  {x.priority}
                </span>
                <div>
                  <p className="font-medium">{x.title}</p>
                  <p className="text-slate-600">{x.rationale}</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {x.check_id} · owner: {x.owner_role.replace('_', ' ')} · due by {date(x.due_by)}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
      <div>
        <h3 className="font-semibold mb-2">Score breakdown</h3>
        <table className="w-full text-sm">
          <tbody>
            <tr><td className="py-1">Start</td><td className="text-right">100</td></tr>
            {a.score.penalties.map((p) => (
              <tr key={p.check_id} className="text-red-800">
                <td className="py-1">{p.check_id} {p.status} ({p.severity})</td>
                <td className="text-right">−{p.points}</td>
              </tr>
            ))}
            <tr className="border-t border-slate-200 font-semibold">
              <td className="py-1">Score</td><td className="text-right">{a.score.score} · {a.score.tier}</td>
            </tr>
          </tbody>
        </table>
        <p className="text-xs text-slate-500 mt-2">{a.score.note}</p>
      </div>
    </div>
  )
}

export default function InvoiceDetail() {
  const { id } = useParams()
  const [tab, setTab] = useState('checks')
  const { data, error, loading, reload } = useApi(() => load(id), [id])

  if (loading) return <Loading label="Loading invoice…" />
  if (error) {
    return (
      <div className="space-y-3">
        <ErrorBox error={error} onRetry={error.status === 404 ? undefined : reload} />
        <Link to="/" className="text-blue-700 underline text-sm">Back to the dashboard</Link>
      </div>
    )
  }
  const { invoice: inv, threshold } = data
  const a = inv.analysis
  if (!a) {
    return <ErrorBox error={new Error('This invoice has not been processed yet.')} onRetry={reload} />
  }

  return (
    <section className="space-y-4">
      <Header inv={inv} a={a} />

      <Card title="Evidence graph" aside="How the documents support this invoice">
        <EvidenceGraph graph={a.graph} checks={a.checks} />
      </Card>

      <Card>
        <div role="tablist" className="flex flex-wrap gap-1 border-b border-slate-200 mb-4 -mt-1">
          {TABS.map(([key, labelText]) => (
            <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
                    className={`px-3 py-2 text-sm -mb-px border-b-2 ${tab === key
                      ? 'border-slate-900 font-medium' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>
              {labelText}
            </button>
          ))}
        </div>
        <div role="tabpanel">
          {tab === 'checks' && <Checks checks={a.checks} />}
          {tab === 'actions' && <ActionsAndScore a={a} />}
          {tab === 'documents' && <DocumentFields documents={inv.documents} threshold={threshold} />}
          {tab === 'followups' && <FollowupsPanel invoiceId={inv.id} />}
          {tab === 'pack' && <DisputePackPanel invoiceId={inv.id} />}
        </div>
      </Card>
    </section>
  )
}
