// One description per tool, shared by the hover cards (InfoHint) and the How it works page,
// so the two never disagree. Rule values quoted here (45/15 days, 3 x bank rate, 0.60) mirror
// backend/app/rules/config.yaml; they are explanations, never used in a calculation.

export const TOOLS = {
  dashboard: {
    title: 'Dashboard',
    summary: 'Every open invoice at a glance: money at risk, what to fix first, and how each invoice scores.',
    points: [
      'Cash at risk in the next 30 and 60 days',
      'Top 5 actions across all invoices, most serious first',
      'Every invoice with its estimated due date, score and tier',
    ],
    anchor: 'tools',
  },
  upload: {
    title: 'New package',
    summary: 'Drop in every document for one invoice. Each file is classified, read and cross-checked.',
    points: [
      'PDF, PNG or JPG, up to 15 MB each',
      'Document type detected from first-page keywords, then the file name; change it if wrong',
      'Processing takes milliseconds per package',
    ],
    anchor: 'step-upload',
  },
  buyers: {
    title: 'Buyer reliability',
    summary: "How each buyer has paid this supplier before, from the supplier's own history. Not a credit rating.",
    points: [
      'Reliable: median ≤ 5 days late and ≤ 10 % over 30 days late',
      'Slow: median ≥ 20 days late or ≥ 40 % over 30 days late',
      'Needs at least 5 paid invoices; the demo history is synthetic',
    ],
    anchor: 'tool-buyers',
  },
  howItWorks: {
    title: 'How it works',
    summary: 'The whole flow on one page: documents, checks, the MSMED rules, the score and every tool.',
    points: ['Plain-language definitions', 'A worked example with real numbers'],
    anchor: 'top',
  },
  evidenceGraph: {
    title: 'Evidence graph',
    summary: 'The invoice in the middle, each supporting document around it. Every link is coloured by the checks behind it.',
    points: [
      '✓ matched · ✕ mismatch · ? missing · ! needs a human check',
      'Click a document or a link to see why',
      'A missing GRN is the most common weak link',
    ],
    anchor: 'tool-graph',
  },
  checks: {
    title: 'Checks',
    summary: '14 deterministic cross-checks between the invoice, PO, challan, e-way bill and GRN.',
    points: [
      'Each returns pass, fail, missing or uncertain',
      'Blocker: can sink a claim · warning: weakens it · info: a note',
      'Unsure values give "uncertain", never a guess',
    ],
    anchor: 'step-checks',
  },
  actions: {
    title: 'Actions & score',
    summary: 'What to fix first, who owns it and by when, plus the readiness score with every penalty listed.',
    points: [
      'Score = 100 − penalties (blocker 25, missing GRN 30, warning 10, uncertain 5)',
      'Low risk ≥ 85 · Medium 60–84 · High < 60',
      'Illustrative: it rates the paperwork, not the buyer',
    ],
    anchor: 'step-score',
  },
  documents: {
    title: 'Documents',
    summary: 'Every field read from every document, with its confidence and the page it came from.',
    points: [
      'Amber = read with low confidence: needs a human check',
      'Values below 0.60 confidence are never used in a calculation',
    ],
    anchor: 'step-extract',
  },
  followups: {
    title: 'Follow-ups',
    summary: 'Ready-to-send reminder drafts timed around the due date. The app never sends them.',
    points: [
      'D−7, D−1, D+3, D+10 and D+25',
      'Friendly or firm tone, for email or WhatsApp',
      'Firm drafts cite the 45-day limit for micro and small suppliers',
    ],
    anchor: 'tool-followups',
  },
  disputePack: {
    title: 'Dispute pack',
    summary: 'A dispute-ready evidence document for a delayed-payment reference (MSME ODR portal).',
    points: [
      '9 sections: summary, facts, documents, timeline, checks, due date, interest, gaps, next step',
      'PDF, or Markdown if the PDF cannot be built',
      'Unverified values print as [to be verified]',
    ],
    anchor: 'tool-pack',
  },
  dueDate: {
    title: 'Estimated due date',
    summary: 'When the buyer must pay under the MSMED Act, worked out from the acceptance date and the terms.',
    points: [
      'Acceptance: GRN date, else challan received date, else deemed (delivery day)',
      'Terms: written terms up to 45 days, or 15 days without written terms',
      'Always an estimate: verify before relying on it',
    ],
    anchor: 'step-law',
  },
  interest: {
    title: 'Statutory interest',
    summary: 'MSMED s.16 interest on late payment: compound with monthly rests at 3 × the RBI bank rate.',
    points: ['Bank rate 5.75 % → 17.25 % a year', 'The formula is shown with every figure', 'Estimate, not legal advice'],
    anchor: 'step-law',
  },
  readiness: {
    title: 'Readiness score',
    summary: 'How claim-ready the paperwork is, from 0 to 100. It does not predict whether the buyer pays.',
    points: ['100 − penalties, kept between 0 and 100', 'Low ≥ 85 · Medium 60–84 · High < 60'],
    anchor: 'step-score',
  },
  openReceivables: {
    title: 'Open receivables',
    summary: 'The total of every open invoice whose amount was read reliably.',
    points: ['Suspected duplicates and unreadable totals are left out and listed'],
    anchor: 'tool-forecast',
  },
  cashAtRisk: {
    title: 'Cash at risk',
    summary: 'Open invoices not expected to be paid inside the window.',
    points: [
      'Expected date = due date + the buyer’s median days late',
      'At risk if: High tier, due date unknown, expected date passed, or beyond the window',
      'The 60-day figure can be lower than the 30-day one: more invoices fall inside a longer window',
    ],
    anchor: 'tool-forecast',
  },
  expected: {
    title: 'Expected in 30 days',
    summary: 'Open invoices whose expected payment date falls in the next 30 days.',
    points: ['Illustrative: based on synthetic demo history'],
    anchor: 'tool-forecast',
  },
  forecast: {
    title: 'Cash-at-risk forecast',
    summary: 'Open receivables bucketed by expected payment date: overdue, next 30 days, 31–60, beyond 60, unknown.',
    points: ['Transparent heuristic, not machine learning', 'Opens as a table on phones'],
    anchor: 'tool-forecast',
  },
  topActions: {
    title: 'Top actions',
    summary: 'The five most urgent fixes across all invoices, ranked by severity, then date.',
    points: ['Overdue invoices say "act now · payment overdue since …"', 'Click one to open its invoice'],
    anchor: 'step-score',
  },
  tiers: {
    title: 'Risk tiers',
    summary: 'Invoices grouped by readiness tier, with the total amount in each.',
    points: ['Same population as the forecast, so the totals agree'],
    anchor: 'step-score',
  },
}

/** Order of the tool cards on the How it works page. */
export const TOOL_ORDER = ['upload', 'evidenceGraph', 'checks', 'actions', 'documents', 'followups',
  'disputePack', 'dashboard', 'forecast', 'buyers']
