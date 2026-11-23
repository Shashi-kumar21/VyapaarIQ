import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../lib/api.js'
import { fileProblem } from '../lib/upload.js'
import Dashboard from './Dashboard.jsx'
import NewPackage from './NewPackage.jsx'

vi.mock('../lib/api.js', () => ({
  api: {
    listInvoices: vi.fn(), forecast: vi.fn(), topActions: vi.fn(),
    uploadPackage: vi.fn(), processPackage: vi.fn(),
  },
}))

const forecastFor = (days, atRisk) => ({
  as_of: '2026-11-23', days, window_end: days === 30 ? '2026-12-23' : '2027-01-22',
  totals: { open: 262921.5, expected_in_window: 240000, at_risk: atRisk, count: 2, excluded_count: 1, excluded_amount: 5 },
  buckets: [], invoices: [], excluded: [{ id: 63, reason: 'duplicate_suspect (C14 failed)' }], formula: 'expected = due + median late', note: 'Illustrative forecast.',
})

beforeEach(() => vi.resetAllMocks())
afterEach(cleanup)

function renderAt(path, element) {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/" element={element} />
        <Route path="/packages/new" element={element} />
        <Route path="/invoices/:id" element={<p>invoice page</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('Dashboard', () => {
  it('shows receivables, cash at risk, tiers and top actions from the API', async () => {
    api.listInvoices.mockResolvedValue([
      { id: 61, invoice_no: 'SPC/26-27/0107', buyer_name: 'Kaveri', amount_total: 22921.5, due_date: '2026-10-13',
        status: 'open', readiness_score: 70, risk_tier: 'Medium' },
      { id: 62, invoice_no: null, buyer_name: null, amount_total: null, due_date: null,
        status: 'open', readiness_score: 45, risk_tier: 'High' },
      { id: 63, invoice_no: 'DUP-1', buyer_name: 'Kaveri', amount_total: 99999, due_date: '2026-12-01',
        status: 'open', readiness_score: 40, risk_tier: 'High' },
    ])
    api.forecast.mockImplementation((d) => Promise.resolve(forecastFor(d, d === 30 ? 22921.5 : 30000)))
    api.topActions.mockResolvedValue([
      { invoice_id: 61, invoice_no: 'SPC/26-27/0107', buyer_name: 'Kaveri', check_id: 'C10', severity: 'blocker',
        title: 'Request GRN / acceptance acknowledgement', due_by: '2026-11-23' },
    ])
    renderAt('/', <Dashboard />)
    expect(await screen.findByText('₹2,62,922')).toBeTruthy() // open receivables, half-even
    expect(screen.getAllByText('₹22,922').length).toBeGreaterThan(0) // at risk 30 days
    expect(screen.getByText('₹30,000')).toBeTruthy() // at risk 60 days
    expect(screen.getByText('Request GRN / acceptance acknowledgement').closest('a').getAttribute('href'))
      .toBe('/invoices/61')
    expect(screen.getByText(/1 invoice\(s\) left out \(/)).toBeTruthy()
    // tier card leaves out the forecast-excluded duplicate (id 63): High = 1 invoice, unverified amount
    expect(screen.getByText(/Excludes 1 invoice\(s\) left out of the forecast/)).toBeTruthy()
    const tierCard = screen.getByText('Invoices by risk tier').closest('section').textContent
    expect(tierCard).not.toContain('₹99,999') // the duplicate stays in the table, not in the totals
    expect(tierCard).toContain('1 · ₹0') // High: only the unverified-amount invoice 62
    expect(screen.getByText('to verify')).toBeTruthy() // unverified amount is never shown as a number
    expect(screen.getByText('unverified')).toBeTruthy()
    expect(api.topActions).toHaveBeenCalledWith(5)
  })

  it('shows an empty state with an upload link', async () => {
    api.listInvoices.mockResolvedValue([])
    api.forecast.mockImplementation((d) => Promise.resolve(forecastFor(d, 0)))
    api.topActions.mockResolvedValue([])
    renderAt('/', <Dashboard />)
    expect(await screen.findByText('No invoices yet')).toBeTruthy()
    expect(screen.getByText('Upload a package').getAttribute('href')).toBe('/packages/new')
  })

  it('shows the backend error with a retry button', async () => {
    api.listInvoices.mockRejectedValue(new Error('Cannot reach the backend at http://localhost:8000.'))
    api.forecast.mockResolvedValue(forecastFor(30, 0))
    api.topActions.mockResolvedValue([])
    renderAt('/', <Dashboard />)
    expect(await screen.findByText(/Cannot reach the backend/)).toBeTruthy()
    api.listInvoices.mockResolvedValue([])
    fireEvent.click(screen.getByText('Try again'))
    expect(await screen.findByText('No invoices yet')).toBeTruthy()
  })
})

describe('New package', () => {
  const pdf = (name, size = 10) => new File(['x'.repeat(size)], name, { type: 'application/pdf' })

  it('validates files like the backend', () => {
    expect(fileProblem(pdf('a.pdf'))).toBeNull()
    expect(fileProblem(new File(['x'], 'notes.txt'))).toMatch(/unsupported/)
    expect(fileProblem(new File([], 'empty.pdf'))).toMatch(/empty/)
  })

  it('uploads with chosen types, processes, then opens the invoice', async () => {
    api.uploadPackage.mockResolvedValue({ id: 7 })
    api.processPackage.mockResolvedValue({ invoice_id: 61, status: 'done' })
    renderAt('/packages/new', <NewPackage />)
    fireEvent.change(screen.getByTestId('file-input'), {
      target: { files: [pdf('PKG07_invoice.pdf'), pdf('scan.pdf'), new File(['x'], 'notes.txt')] },
    })
    expect(screen.getByRole('alert').textContent).toMatch(/notes.txt: unsupported/)
    fireEvent.change(screen.getByLabelText('Document type for scan.pdf'), { target: { value: 'grn' } })
    fireEvent.change(screen.getByPlaceholderText(/Used only if the buyer/), { target: { value: ' Kaveri ' } })
    fireEvent.click(screen.getByText('Process package'))
    expect(await screen.findByText('invoice page')).toBeTruthy()
    const [files, opts] = api.uploadPackage.mock.calls[0]
    expect(files.map((f) => f.name)).toEqual(['PKG07_invoice.pdf', 'scan.pdf'])
    expect(opts).toEqual({ buyerName: 'Kaveri', docTypes: [null, 'grn'] })
    expect(api.processPackage).toHaveBeenCalledWith(7)
  })

  it('keeps the page and explains a processing failure', async () => {
    api.uploadPackage.mockResolvedValue({ id: 8 })
    api.processPackage.mockRejectedValue(new Error('No invoice found in the package.'))
    renderAt('/packages/new', <NewPackage />)
    fireEvent.change(screen.getByTestId('file-input'), { target: { files: [pdf('po.pdf')] } })
    fireEvent.click(screen.getByText('Process package'))
    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toMatch(
        /^Package #8 was uploaded but processing failed: No invoice found in the package\. Retrying re-runs/))
    // retry re-runs /process on the same package; it does not upload a duplicate
    api.processPackage.mockResolvedValue({ invoice_id: 70, status: 'done' })
    fireEvent.click(screen.getByText('Retry processing'))
    expect(await screen.findByText('invoice page')).toBeTruthy()
    expect(api.uploadPackage).toHaveBeenCalledTimes(1)
    expect(api.processPackage.mock.calls.map((c) => c[0])).toEqual([8, 8])
  })

  it('uploads again after the inputs change following a failure', async () => {
    api.uploadPackage.mockResolvedValueOnce({ id: 8 }).mockResolvedValueOnce({ id: 9 })
    api.processPackage.mockRejectedValueOnce(new Error('No invoice found in the package.'))
      .mockResolvedValueOnce({ invoice_id: 71 })
    renderAt('/packages/new', <NewPackage />)
    fireEvent.change(screen.getByTestId('file-input'), { target: { files: [pdf('po.pdf')] } })
    fireEvent.click(screen.getByText('Process package'))
    await screen.findByText('Retry processing')
    fireEvent.change(screen.getByTestId('file-input'), { target: { files: [pdf('invoice.pdf')] } })
    fireEvent.click(screen.getByText('Process package'))
    expect(await screen.findByText('invoice page')).toBeTruthy()
    expect(api.uploadPackage).toHaveBeenCalledTimes(2)
    expect(api.processPackage.mock.calls.map((c) => c[0])).toEqual([8, 9])
  })

  it('disables Process until a file is added and lets you remove files', () => {
    renderAt('/packages/new', <NewPackage />)
    expect(screen.getByText('Process package').disabled).toBe(true)
    fireEvent.change(screen.getByTestId('file-input'), { target: { files: [pdf('a.pdf')] } })
    expect(screen.getByText('Process package').disabled).toBe(false)
    fireEvent.click(screen.getByLabelText('Remove a.pdf'))
    expect(screen.queryByText('a.pdf')).toBeNull()
  })
})
