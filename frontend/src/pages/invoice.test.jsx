import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../lib/api.js'
import InvoiceDetail from './InvoiceDetail.jsx'

vi.mock('../lib/api.js', () => ({
  api: { getInvoice: vi.fn(), health: vi.fn(), listFollowups: vi.fn(), generateFollowups: vi.fn(), disputePack: vi.fn() },
}))

// Shape taken from the real /api/invoices/{id} response for PKG07 (GRN missing), trimmed.
const f = (value, confidence = 1, source_page = 1) => ({ value, confidence, source_page })
const INVOICE = {
  id: 61, invoice_no: 'SPC/26-27/0107', invoice_date: '2026-09-10', buyer_name: 'Kaveri Auto Assemblies Pvt Ltd',
  amount_total: 22921.5, due_date: '2026-10-13', readiness_score: 70, risk_tier: 'Medium', processing_ms: 1234,
  documents: [
    { id: 2, filename: 'PKG07_invoice.pdf', doc_type: 'invoice', extractor: 'text', fallback: false,
      extraction_conf: 0.84, error: null,
      fields: { doc_type: 'invoice', filename: 'PKG07_invoice.pdf', invoice_no: f('SPC/26-27/0107'),
        total: f(22921.5, 0.4), invoice_date: f('2026-09-10'),
        line_items: f([{ desc: 'SS Hex Bolt M12x50', qty: 50, rate: 18.5 }]) } },
    { id: 3, filename: 'broken.pdf', doc_type: 'other', error: 'File is not a readable PDF.', fields: null },
  ],
  analysis: {
    checks: [
      { check_id: 'C01', name: 'Invoice ↔ PO reference', status: 'pass', severity: 'blocker', detail: 'PO matches.' },
      { check_id: 'C10', name: 'GRN / acceptance', status: 'missing', severity: 'blocker', detail: 'No GRN in package.' },
      { check_id: 'C07', name: 'Receiving evidence', status: 'uncertain', severity: 'warning', detail: 'Stamp unreadable.' },
      { check_id: 'C03', name: 'Line items vs PO', status: 'missing', severity: 'info', detail: 'Skipped: no PO in the package (see C01).' },
    ],
    score: { score: 65, tier: 'Medium', note: 'Illustrative readiness score, not a prediction of buyer payment.',
      penalties: [{ check_id: 'C10', status: 'missing', severity: 'blocker', points: 30 },
                  { check_id: 'C07', status: 'uncertain', severity: 'warning', points: 5 }] },
    due: { acceptance_basis: 'challan_received', due_date: '2026-10-13', uncertain: false,
      reasoning: 'No GRN; acceptance 2026-09-13 taken from the received date on the delivery challan.' },
    interest: { computable: true, interest: 452.05, days_late: 41, as_of: '2026-11-23', annual_rate_pct: 17.25,
      formula: 'P x (1 + 17.25%/12)^1 …', note: 'Estimated statutory interest (MSMED s.16). Not legal advice.' },
    actions: [{ priority: 1, check_id: 'C10', title: 'Request GRN / acceptance acknowledgement',
      rationale: 'Acceptance starts the MSMED payment clock.', due_by: '2026-11-23', owner_role: 'sales' }],
    graph: {
      nodes: [
        { id: 'inv', type: 'invoice', label: 'SPC/26-27/0107 ₹22,922', status: 'ok', doc_no: 'SPC/26-27/0107' },
        { id: 'po', type: 'po', label: 'Purchase order KAA/PO/2627/1142', status: 'ok' },
        { id: 'challan', type: 'challan', label: 'Delivery challan No. ? (verify)', status: 'uncertain' },
        { id: 'grn', type: 'grn', label: 'GRN / acceptance', status: 'missing' },
      ],
      edges: [
        { from: 'inv', to: 'po', status: 'matched', confidence: 1, note: 'PO matches.', check_ids: ['C01'] },
        { from: 'inv', to: 'challan', status: 'uncertain', confidence: 0.5, note: 'Stamp unreadable.', check_ids: ['C07'] },
        { from: 'inv', to: 'grn', status: 'missing', confidence: 0, note: 'No GRN in package.', check_ids: ['C10'] },
      ],
    },
    extractor_used: 'fixture,text', fallback_used: true,
  },
}

beforeEach(() => {
  vi.resetAllMocks()
  api.health.mockResolvedValue({ status: 'ok', uncertain_below: 0.6 })
})
afterEach(cleanup)

function renderInvoice(id = '61') {
  return render(
    <MemoryRouter initialEntries={[`/invoices/${id}`]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes><Route path="/invoices/:id" element={<InvoiceDetail />} /></Routes>
    </MemoryRouter>,
  )
}

describe('Invoice detail', () => {
  it('shows the header with estimated due date, score, fallback badge and interest', async () => {
    api.getInvoice.mockResolvedValue(INVOICE)
    renderInvoice()
    expect(await screen.findByRole('heading', { name: 'SPC/26-27/0107' })).toBeTruthy()
    expect(api.getInvoice).toHaveBeenCalledWith('61')
    expect(screen.getByText('Due date (estimated)')).toBeTruthy()
    expect(screen.getByText('13 Oct 2026')).toBeTruthy()
    expect(screen.getByText('from challan received date')).toBeTruthy()
    expect(screen.getAllByText('demo fallback').length).toBeGreaterThan(0)
    expect(screen.getByText('processed in 1.2 s')).toBeTruthy() // T3.10
    expect(screen.getByText('₹452')).toBeTruthy()
    expect(screen.getByText(/Not legal advice/)).toBeTruthy()
  })

  it('draws the evidence graph with a status per node and edge, and explains a clicked edge', async () => {
    api.getInvoice.mockResolvedValue(INVOICE)
    const { container } = renderInvoice()
    await screen.findByRole('img', { name: /Evidence graph/ })
    const status = (sel) => container.querySelector(sel).getAttribute('data-status')
    expect(status('[data-node="grn"]')).toBe('missing')
    expect(status('[data-node="challan"]')).toBe('uncertain')
    expect(status('[data-edge="po"]')).toBe('matched')
    expect(status('[data-edge="grn"]')).toBe('missing')
    fireEvent.click(container.querySelector('[data-edge="grn"]'))
    const panel = screen.getByText(/Invoice → GRN \/ acceptance/).parentElement
    expect(within(panel).getByText(/C10/)).toBeTruthy()
    expect(within(panel).getAllByText(/No GRN in package/).length).toBeGreaterThan(0)
  })

  it('lists failing checks first, then actions with the score breakdown', async () => {
    api.getInvoice.mockResolvedValue(INVOICE)
    const { container } = renderInvoice()
    await screen.findByText('2 of 4 checks need attention.') // the skipped C03 is not counted
    const order = [...container.querySelectorAll('[data-check]')].map((el) => el.getAttribute('data-check'))
    expect(order).toEqual(['C10', 'C07', 'C03', 'C01'])
    const c03 = container.querySelector('[data-check="C03"]')
    expect(within(c03).getByText('skipped')).toBeTruthy()
    expect(within(c03).queryByText('info')).toBeNull()
    fireEvent.click(screen.getByRole('tab', { name: 'Actions & score' }))
    expect(screen.getByText('Request GRN / acceptance acknowledgement')).toBeTruthy()
    expect(screen.getByText('−30')).toBeTruthy()
    expect(screen.getByText('−5')).toBeTruthy()
    expect(screen.getByText('65 · Medium')).toBeTruthy()
  })

  it('marks low-confidence fields amber using the threshold from the API', async () => {
    api.getInvoice.mockResolvedValue(INVOICE)
    const { container } = renderInvoice()
    await screen.findByRole('heading', { name: 'SPC/26-27/0107' })
    fireEvent.click(screen.getByRole('tab', { name: 'Documents' }))
    const unsure = [...container.querySelectorAll('[data-unsure]')]
    expect(unsure).toHaveLength(1)
    expect(unsure[0].textContent).toMatch(/Total.*needs human check · 40%/)
    expect(screen.getByText('1 field(s) need human check')).toBeTruthy()
    expect(screen.getByText('File is not a readable PDF.')).toBeTruthy()
    expect(screen.getByText('SS Hex Bolt M12x50')).toBeTruthy()
    // a stricter threshold from config flags more fields; nothing is hard-coded in the UI
    cleanup()
    api.health.mockResolvedValue({ status: 'ok', uncertain_below: 1.01 })
    const second = renderInvoice()
    await screen.findByRole('heading', { name: 'SPC/26-27/0107' })
    fireEvent.click(screen.getByRole('tab', { name: 'Documents' }))
    expect(second.container.querySelectorAll('[data-unsure]').length).toBe(4)
  })

  it('shows unverified amount and buyer instead of numbers', async () => {
    api.getInvoice.mockResolvedValue({ ...INVOICE, amount_total: null, buyer_name: null })
    renderInvoice()
    expect(await screen.findByText('to be verified')).toBeTruthy()
    expect(screen.getByText('buyer unverified')).toBeTruthy()
  })

  it('shows a calm state, not an error, for a seeded invoice without checks (B-10)', async () => {
    api.getInvoice.mockResolvedValue({ ...INVOICE, id: 3, invoice_no: 'SPC/HIST/003', synthetic: true, analysis: null })
    renderInvoice('3')
    expect(await screen.findByText('Invoice SPC/HIST/003 has no checks')).toBeTruthy()
    expect(screen.getByText(/seeded \(synthetic\) payment history/)).toBeTruthy()
    expect(screen.queryByText('Try again')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('shows a clear not-found error', async () => {
    api.getInvoice.mockRejectedValue(Object.assign(new Error('Invoice not found.'), { status: 404 }))
    renderInvoice('999')
    expect(await screen.findByText('Invoice not found.')).toBeTruthy()
    expect(screen.queryByText('Try again')).toBeNull()
    expect(screen.getByText('Back to the dashboard')).toBeTruthy()
  })
})
