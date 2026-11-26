import { ArrowLeft, ArrowUpRight, FileSearch, FileText, FileX2, Gauge, ListChecks, Mail } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router'
import DisputePackPanel from '../components/DisputePackPanel.jsx'
import DocumentFields from '../components/DocumentFields.jsx'
import EvidenceGraph from '../components/EvidenceGraph.jsx'
import FollowupsPanel from '../components/FollowupsPanel.jsx'
import InfoHint from '../components/InfoHint.jsx'
import { Card, Empty, ErrorBox, Loading, SeverityChip, StatusChip, TierBadge } from '../components/ui.jsx'
import { api } from '../lib/api.js'
import { deadlineText } from '../lib/deadline.js'
import { date, inr } from '../lib/format.js'
import { TOOLS } from '../lib/tools.js'
import { useApi } from '../lib/useApi.js'
import { btn } from '../lib/styles.js'

// Invoice detail (BUILD_SPEC §13.3, tasks T2.13–T2.15, T3.12): the demo screen.

const SEV_ORDER = { blocker: 0, warning: 1, info: 2 }
const BASIS = { grn: 'GRN date', challan_received: 'challan received date', deemed: 'deemed acceptance', unknown: 'unknown' }
// [key, label, icon, tool description (lib/tools.js)]
const TABS = [
  ['checks', 'Checks', ListChecks, 'checks'], ['actions', 'Actions & score', Gauge, 'actions'],
  ['documents', 'Documents', FileSearch, 'documents'], ['followups', 'Follow-ups', Mail, 'followups'],
  ['pack', 'Dispute pack', FileText, 'disputePack'],
]

async function load(id) {
  const [invoice, health] = await Promise.all([api.getInvoice(id), api.health()])
  return { invoice, threshold: health.uncertain_below ?? 0.6 }
}

/** "missing" on an info check means the check was skipped (e.g. C06/C07 with no challan). */
function shownStatus(c) {
  return c.status === 'missing' && c.severity === 'info' ? 'skipped' : c.status
}

function Fact({ label, tool, children, sub }) {
  return (
    <div className="min-w-0 rounded-xl bg-paper px-4 py-3">
      <div className="flex items-center gap-1 text-xs font-medium uppercase tracking-wide text-muted">
        {label}{tool && <InfoHint tool={tool} />}
      </div>
      <div className="mt-1 font-display text-xl font-bold tabular-nums text-ink">{children}</div>
      {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
    </div>
  )
}

function Header({ inv, a }) {
  const due = a.due
  const interest = a.interest
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Link to="/" className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-accent">
            <ArrowLeft aria-hidden="true" className="size-3.5" />Dashboard
          </Link>
          <div className="mt-2 text-xs font-semibold uppercase tracking-[0.14em] text-accent">Invoice</div>
          <h1 className="font-mono text-2xl font-semibold tracking-tight text-ink">{inv.invoice_no || <span className="text-unsure">No. to verify</span>}</h1>
          <div className="mt-1 text-sm text-muted">
            {inv.buyer_name || <span className="text-unsure">buyer unverified</span>} · dated {date(inv.invoice_date)}
          </div>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="rounded-full bg-paper px-2.5 py-1 text-muted ring-1 ring-inset ring-line">extractor: {a.extractor_used || '—'}</span>
          {a.fallback_used && <span className="rounded-full bg-purple-50 px-2.5 py-1 text-purple-800 ring-1 ring-inset ring-purple-600/20">demo fallback</span>}
          {inv.processing_ms != null && (
            <span className="rounded-full bg-paper px-2.5 py-1 text-muted ring-1 ring-inset ring-line" title="Time to extract and analyse this package">
              processed in {inv.processing_ms < 1000 ? `${inv.processing_ms} ms` : `${(inv.processing_ms / 1000).toFixed(1)} s`}
            </span>
          )}
        </div>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Fact label="Amount">
          {inv.amount_total === null ? <span className="text-unsure">to be verified</span> : inr(inv.amount_total)}
        </Fact>
        <Fact label="Due date (estimated)" tool="dueDate" sub={<>
          from {BASIS[due.acceptance_basis] || due.acceptance_basis}
          {due.acceptance_basis === 'deemed' && <span className="ml-1 font-medium text-unsure">· verify</span>}
          {due.uncertain && <span className="ml-1 font-medium text-unsure">· uncertain</span>}
        </>}>{date(due.due_date)}</Fact>
        <Fact label="Readiness" tool="readiness" sub="Illustrative">
          <span className="flex items-center gap-2">{a.score.score}<TierBadge tier={a.score.tier} /></span>
        </Fact>
        <Fact label="Interest to date" tool="interest"
              sub={interest?.computable ? `${interest.days_late} day(s) late · ${interest.annual_rate_pct}% a year` : 'not computable'}>
          {interest?.computable ? inr(interest.interest) : '—'}
        </Fact>
      </div>

      <details className="mt-4 text-sm">
        <summary className="cursor-pointer font-medium text-accent">How the due date and interest were worked out</summary>
        <p className="mt-2">{due.reasoning}</p>
        {interest && (
          <p className="mt-2">
            {interest.computable
              ? <>Estimated statutory interest: <b>{inr(interest.interest)}</b> ({interest.days_late} day(s) late as of {date(interest.as_of)}, {interest.annual_rate_pct}% a year). <span className="text-muted">{interest.formula}</span></>
              : <span className="text-muted">{interest.formula}</span>}
          </p>
        )}
        <p className="mt-1 text-xs text-muted">{interest?.note || 'Estimated; not legal advice. Verify before use.'}</p>
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
      <p className="mb-3 text-sm text-muted">{open} of {checks.length} checks need attention.</p>
      <ul className="divide-y divide-line">
        {sorted.map((c) => (
          <li key={c.check_id} className="flex items-start gap-3 py-3 text-sm" data-check={c.check_id}>
            <span className="w-9 pt-0.5 font-mono text-xs text-muted">{c.check_id}</span>
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{c.name}</span>
                <StatusChip status={shownStatus(c)} />
                {!['pass', 'skipped'].includes(shownStatus(c)) && <SeverityChip severity={c.severity} />}
              </div>
              <p className={`mt-0.5 ${['pass', 'skipped'].includes(shownStatus(c)) ? 'text-muted' : 'text-ink'}`}>{c.detail}</p>
              {c.explanation && <p className="mt-0.5 italic text-muted">{c.explanation}</p>}
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
        <h3 className="mb-3 font-display font-semibold text-ink">Recommended actions</h3>
        {a.actions.length === 0 ? (
          <p className="text-sm text-muted">Nothing to do. Every check passed.</p>
        ) : (
          <ol className="space-y-3">
            {a.actions.map((x) => (
              <li key={`${x.check_id}-${x.priority}`} className="text-sm flex gap-3">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-ink font-mono text-xs text-white">
                  {x.priority}
                </span>
                <div>
                  <p className="font-medium">{x.title}</p>
                  <p className="text-muted">{x.rationale}</p>
                  <p className="mt-0.5 text-xs text-muted">
                    {x.check_id} · owner: {x.owner_role.replace('_', ' ')} · {deadlineText(x.due_by, a.due?.due_date)}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
      <div>
        <h3 className="mb-3 font-display font-semibold text-ink">Score breakdown</h3>
        <table className="w-full rounded-xl bg-paper text-sm tabular-nums">
          <tbody>
            <tr><td className="px-3 py-1.5">Start</td><td className="px-3 text-right">100</td></tr>
            {a.score.penalties.map((p) => (
              <tr key={p.check_id} className="text-red-800">
                <td className="px-3 py-1.5">{p.check_id} {p.status} ({p.severity})</td>
                <td className="px-3 text-right">−{p.points}</td>
              </tr>
            ))}
            <tr className="border-t border-line font-semibold">
              <td className="px-3 py-1.5">Score</td><td className="px-3 text-right">{a.score.score} · {a.score.tier}</td>
            </tr>
          </tbody>
        </table>
        <p className="mt-2 text-xs text-muted">{a.score.note}</p>
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
        <Link to="/" className={`${btn.link} text-sm`}>Back to the dashboard</Link>
      </div>
    )
  }
  const { invoice: inv, threshold } = data
  const a = inv.analysis
  if (!a) {
    // B-10: seeded history invoices (and any invoice without an analysis) have nothing to check;
    // that is a state, not an error, so no "Try again".
    return (
      <div className="space-y-3">
        <Empty title={`Invoice ${inv.invoice_no || `#${inv.id}`} has no checks`} icon={FileX2}
               action={<Link to="/" className={btn.secondary}><ArrowLeft aria-hidden="true" className="size-4" />Back to the dashboard</Link>}>
          {inv.synthetic
            ? 'It is part of the seeded (synthetic) payment history used for buyer profiles, so it has no document package.'
            : 'Its document package has not been processed yet. Upload and process it on New package.'}
        </Empty>
      </div>
    )
  }

  const current = TABS.find(([k]) => k === tab)
  const openChecks = a.checks.filter((c) => !['pass', 'skipped'].includes(shownStatus(c))).length
  return (
    <section className="space-y-4">
      <Header inv={inv} a={a} />

      <Card title="Evidence graph" tool="evidenceGraph" aside="How the documents support this invoice">
        <EvidenceGraph graph={a.graph} checks={a.checks} />
      </Card>

      <Card>
        <div role="tablist" aria-label="Invoice sections" className="-mt-1 flex flex-wrap gap-1 rounded-xl bg-paper p-1">
          {TABS.map(([key, labelText, Icon, tool]) => (
            <InfoHint key={key} tool={tool}>
              {(hint) => (
                <button type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
                        onMouseEnter={hint.onMouseEnter} onMouseLeave={hint.onMouseLeave}
                        className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${tab === key
                          ? 'bg-surface text-ink shadow-card ring-1 ring-line' : 'text-muted hover:bg-surface/60 hover:text-ink'}`}>
                  <Icon aria-hidden="true" className="size-4" />{labelText}
                  {key === 'checks' && openChecks > 0 && (
                    <span aria-hidden="true" className="rounded-full bg-red-50 px-1.5 text-xs font-semibold text-bad ring-1 ring-inset ring-red-600/20">{openChecks}</span>
                  )}
                </button>
              )}
            </InfoHint>
          ))}
        </div>
        <p className="mb-4 mt-3 flex flex-wrap items-center gap-x-2 text-xs text-muted">
          {TOOLS[current[3]].summary}
          <Link to={`/how-it-works#${TOOLS[current[3]].anchor}`} className="inline-flex items-center gap-0.5 font-medium text-accent hover:underline">
            Learn more<ArrowUpRight aria-hidden="true" className="size-3" />
          </Link>
        </p>
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
