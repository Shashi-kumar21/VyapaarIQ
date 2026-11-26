import {
  ArrowRight, BadgeIndianRupee, BookOpen, CalendarClock, FileCheck2, FilePlus2, FileSearch, FileText,
  Gauge, LayoutDashboard, LineChart, ListChecks, Mail, Network, ScanText, ShieldCheck, Users,
} from 'lucide-react'
import { useEffect } from 'react'
import { Link, useLocation } from 'react-router'
import { PageHeader } from '../components/ui.jsx'
import { TOOLS, TOOL_ORDER } from '../lib/tools.js'
import { btn } from '../lib/styles.js'

// How it works (D-43): the in-app version of docs/tutorial.md. Tool cards render from the same
// lib/tools.js entries as the hover cards. Rule values mirror backend/app/rules/config.yaml.

const STEPS = [
  { id: 'step-upload', icon: FilePlus2, title: 'Upload the package',
    body: 'Drop in every document for one invoice: invoice, PO, delivery challan or LR, e-way bill, GRN and any contract. Each file is classified from its first-page keywords, then its file name; you can change the type.' },
  { id: 'step-extract', icon: ScanText, title: 'Read every field',
    body: 'Each document becomes fields that carry a value, a confidence (0–1) and the page it came from. Anything read below 0.60 confidence is shown amber as "needs human check" and is never used in a calculation.' },
  { id: 'step-checks', icon: ListChecks, title: 'Run 14 checks',
    body: 'Deterministic cross-checks between the documents: references, amounts and GST, quantities, buyer identity, delivery and acceptance proof, dates, terms, Udyam and duplicates. An LLM never changes a result.' },
  { id: 'step-score', icon: Gauge, title: 'Score and rank actions',
    body: 'Readiness = 100 − penalties (blocker 25, missing GRN 30, warning 10, uncertain 5). Low risk ≥ 85, Medium 60–84, High < 60. Every finding becomes an action with an owner and a date, most serious first.' },
  { id: 'step-law', icon: CalendarClock, title: 'Apply the MSMED rules',
    body: 'Work out the acceptance date, the statutory due date and the interest building up, and show the rule used for each. Then build follow-ups, the forecast and the dispute pack from the same analysis.' },
]

const CHECKS = [
  ['C01', 'Invoice ↔ PO reference', 'blocker'], ['C02', 'Amount reconciliation (PO value, GST math)', 'blocker'],
  ['C03', 'Line items vs PO', 'warning / blocker'], ['C04', 'Same buyer name and GSTIN everywhere', 'blocker'],
  ['C05', 'Delivery proof exists', 'blocker'], ['C06', 'Delivered ≥ invoiced quantity', 'blocker'],
  ['C07', 'Receiver stamp or signature', 'warning'], ['C08', 'Document dates in order', 'warning'],
  ['C09', 'E-way bill above ₹50,000', 'warning'], ['C10', 'GRN / written acceptance', 'blocker'],
  ['C11', 'Written payment terms', 'warning'], ['C12', 'Terms ≤ 45 days', 'warning'],
  ['C13', 'Supplier Udyam number', 'info'], ['C14', 'Duplicate invoice', 'blocker'],
]

const TOOL_ICON = {
  upload: FilePlus2, evidenceGraph: Network, checks: ListChecks, actions: Gauge, documents: FileSearch,
  followups: Mail, disputePack: FileText, dashboard: LayoutDashboard, forecast: LineChart, buyers: Users,
}
const TOOL_ID = {
  evidenceGraph: 'tool-graph', followups: 'tool-followups', disputePack: 'tool-pack', forecast: 'tool-forecast',
  buyers: 'tool-buyers',
}
const TOOL_WHERE = {
  upload: ['/packages/new', 'Open New package'], dashboard: ['/', 'Open the Dashboard'],
  forecast: ['/', 'See it on the Dashboard'], buyers: ['/buyers', 'Open Buyers'],
}

const GLOSSARY = [
  ['Acceptance', 'The buyer accepting the goods, shown by a GRN or written acceptance. It starts the MSMED payment clock.'],
  ['Deemed acceptance', 'With no written objection within 15 days of delivery, the law treats the delivery day as the day of acceptance (MSMED s.2(b)).'],
  ['GRN', 'Goods Receipt Note: the buyer’s written record that the goods were received and accepted.'],
  ['Delivery challan / LR', 'The dispatch document (or the transporter’s lorry receipt), stamped by the receiver on arrival.'],
  ['GSTIN', 'The 15-character GST registration number of a business.'],
  ['Udyam number', 'The MSME registration number of the supplier.'],
  ['Bank Rate', 'An RBI policy rate (equal to the MSF rate, repo + 0.25 %). MSMED interest is 3 × this rate.'],
  ['Blocker / warning / info', 'How serious a finding is: it can sink a claim / it weakens the claim / it is a note.'],
  ['Uncertain', 'A value was read with low confidence, so the check abstains instead of guessing.'],
  ['MSME ODR portal', 'The government’s Online Dispute Resolution portal for delayed-payment cases of micro and small suppliers.'],
]

function Section({ id, eyebrow, title, children }) {
  return (
    <section id={id} className="scroll-mt-6">
      {eyebrow && <p className="text-xs font-semibold uppercase tracking-[0.14em] text-accent">{eyebrow}</p>}
      <h2 className="mt-1 font-display text-xl font-bold tracking-tight text-ink sm:text-2xl">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  )
}

export default function HowItWorks() {
  const { hash } = useLocation()
  // React Router does not scroll to #anchors on navigation; do it here (Learn more links).
  useEffect(() => {
    if (!hash) return
    const el = document.getElementById(decodeURIComponent(hash.slice(1)))
    el?.scrollIntoView?.({ block: 'start' })
  }, [hash])

  return (
    <div id="top" className="space-y-12">
      <PageHeader eyebrow="How it works" title="From scattered paperwork to a claim you can prove"
                  actions={<Link to="/packages/new" className={btn.primary}>Try it with a package <ArrowRight aria-hidden="true" className="size-4" /></Link>}>
        <p>
          When a buyer pays late, an MSME supplier has to prove the buyer <b className="text-ink">ordered</b>,
          the goods were <b className="text-ink">delivered</b>, and the buyer <b className="text-ink">accepted</b> them.
          VyapaarIQ reads every document behind an invoice, cross-checks them, and shows what is missing,
          what to fix first, when payment is legally due and what interest is building up.
        </p>
      </PageHeader>

      <Section id="flow" eyebrow="The flow" title="Five steps, every one explainable">
        <ol className="grid gap-3 md:grid-cols-5">
          {STEPS.map((s, i) => (
            <li key={s.id} id={s.id} className="scroll-mt-6 rounded-2xl border border-line bg-surface p-4 shadow-card">
              <div className="flex items-center gap-2">
                <span className="flex size-7 items-center justify-center rounded-full bg-ink font-mono text-xs font-semibold text-white">{i + 1}</span>
                <s.icon aria-hidden="true" className="size-4 text-accent" />
              </div>
              <h3 className="mt-3 font-display text-sm font-semibold text-ink">{s.title}</h3>
              <p className="mt-1 text-xs leading-relaxed text-muted">{s.body}</p>
            </li>
          ))}
        </ol>
        <p className="mt-4 flex items-start gap-2 rounded-xl bg-accent-soft px-4 py-3 text-sm text-ink">
          <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-accent" />
          <span><b>Deterministic first.</b> Matching, scoring, due dates and interest are plain code with the same result every time. Rule values live in one config file.</span>
        </p>
      </Section>

      <Section id="checks" eyebrow="Step 3" title="The 14 checks">
        <div className="overflow-x-auto rounded-2xl border border-line bg-surface shadow-card">
          <table className="w-full text-sm">
            <thead className="bg-paper text-left text-xs uppercase tracking-wide text-muted">
              <tr><th className="px-4 py-2">ID</th><th className="px-4 py-2">What it checks</th><th className="px-4 py-2">Severity</th></tr>
            </thead>
            <tbody>
              {CHECKS.map(([id, name, sev]) => (
                <tr key={id} className="border-t border-line">
                  <td className="px-4 py-2 font-mono text-xs text-muted">{id}</td>
                  <td className="px-4 py-2">{name}</td>
                  <td className="px-4 py-2 text-muted">{sev}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section id="law" eyebrow="Step 5" title="Due date and interest under the MSMED Act">
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-line bg-surface p-5 shadow-card">
            <h3 className="flex items-center gap-2 font-display font-semibold text-ink"><CalendarClock aria-hidden="true" className="size-4 text-accent" />Due date</h3>
            <ol className="mt-3 space-y-2 text-sm">
              <li><b>1. Acceptance date:</b> the GRN date; else the received date on a stamped challan; else <i>deemed</i> (the delivery day, labelled “verify”).</li>
              <li><b>2. Terms:</b> written terms, capped at <b>45 days</b>; without written terms, <b>15 days</b> (s.15, micro and small suppliers).</li>
              <li><b>3. Due date</b> = acceptance + terms. Always shown as an estimate, with the rule used.</li>
            </ol>
          </div>
          <div className="rounded-2xl border border-line bg-surface p-5 shadow-card">
            <h3 className="flex items-center gap-2 font-display font-semibold text-ink"><BadgeIndianRupee aria-hidden="true" className="size-4 text-accent" />Interest (s.16)</h3>
            <p className="mt-3 text-sm">Compound with monthly rests at <b>3 × the RBI bank rate</b> (5.75 % → 17.25 % a year):</p>
            <pre className="mt-2 overflow-x-auto rounded-lg bg-paper px-3 py-2 font-mono text-xs text-ink">P × (1 + r/12)^m × (1 + r/12 × d/30) − P</pre>
            <p className="mt-2 text-xs text-muted">P = invoice total, r = annual rate, m = full 30-day months late, d = remaining days. Estimate, not legal advice.</p>
          </div>
        </div>
      </Section>

      <Section id="tools" eyebrow="The tools" title="What each part of the app does">
        <div className="grid gap-4 sm:grid-cols-2">
          {TOOL_ORDER.map((key) => {
            const t = TOOLS[key]
            const Icon = TOOL_ICON[key] || FileCheck2
            const where = TOOL_WHERE[key]
            return (
              <article key={key} id={TOOL_ID[key]} className="scroll-mt-6 flex flex-col rounded-2xl border border-line bg-surface p-5 shadow-card">
                <span className="flex size-9 items-center justify-center rounded-lg bg-accent-soft text-accent"><Icon aria-hidden="true" className="size-4" /></span>
                <h3 className="mt-3 font-display font-semibold text-ink">{t.title}</h3>
                <p className="mt-1 text-sm text-muted">{t.summary}</p>
                <ul className="mt-3 space-y-1 text-xs text-ink/80">
                  {t.points.map((p) => (
                    <li key={p} className="flex gap-2"><span aria-hidden="true" className="mt-1.5 size-1 shrink-0 rounded-full bg-accent" />{p}</li>
                  ))}
                </ul>
                <p className="mt-auto pt-4 text-sm">
                  {where
                    ? <Link to={where[0]} className={btn.link}>{where[1]} →</Link>
                    : <span className="text-muted">On every invoice page</span>}
                </p>
              </article>
            )
          })}
        </div>
      </Section>

      <Section id="example" eyebrow="Worked example" title="PKG07: an invoice with no GRN">
        <div className="overflow-x-auto rounded-2xl border border-line bg-surface shadow-card">
          <table className="w-full text-sm">
            <tbody>
              {[
                ['Documents', 'Invoice, PO and delivery challan. No GRN.'],
                ['Checks', '13 pass; C10 GRN / acceptance is missing (blocker)'],
                ['Score', '100 − 30 = 70 → Medium'],
                ['Acceptance', 'No GRN, so the challan’s received date: 13 Sep 2026'],
                ['Due date', '13 Sep + 30 days of written terms = 13 Oct 2026 (estimated)'],
                ['Interest on 23 Nov 2026', '41 days late at 17.25 %: ₹22,921.50 → about ₹452'],
                ['First action', 'Request the GRN from the buyer’s receiving department: act now, payment overdue since 13 Oct 2026'],
              ].map(([k, v]) => (
                <tr key={k} className="border-t border-line first:border-0">
                  <th scope="row" className="w-48 whitespace-nowrap px-4 py-2 text-left font-medium text-muted">{k}</th>
                  <td className="px-4 py-2">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section id="glossary" eyebrow="Glossary" title="Terms used in the app">
        <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
          {GLOSSARY.map(([term, def]) => (
            <div key={term} className="border-l-2 border-accent/40 pl-3">
              <dt className="font-display text-sm font-semibold text-ink">{term}</dt>
              <dd className="mt-0.5 text-sm text-muted">{def}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <p className="flex items-start gap-2 rounded-xl border border-line bg-surface px-4 py-3 text-xs text-muted">
        <BookOpen aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        Synthetic demo data and fictional companies. Scores are illustrative and do not predict whether a buyer pays.
        Legal figures are estimates, not legal advice: verify before any real use. The full guide with references is
        docs/tutorial.md in the repository.
      </p>
    </div>
  )
}
