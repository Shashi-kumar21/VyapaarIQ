import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ForecastChart from '../components/ForecastChart.jsx'
import { api } from '../lib/api.js'
import Buyers from './Buyers.jsx'

vi.mock('../lib/api.js', () => ({ api: { listBuyers: vi.fn(), health: vi.fn() } }))

beforeEach(() => {
  vi.resetAllMocks()
  api.health.mockResolvedValue({ status: 'ok', min_history: 7 })
})
afterEach(cleanup)

// Shapes from the real /api/buyers response (seeded history).
const profile = (o) => ({ invoices_considered: 10, median_days_late: 0.5, pct_paid_late: 50, pct_paid_over_30_late: 0,
  trend: 'stable', trend_detail: 'median of last 3 = 1 days vs 0 days before', label: 'Reliable',
  note: 'Based only on this supplier\'s own invoice history. Not a credit rating.', ...o })

describe('Buyers page', () => {
  it('lists reliability numbers with labelled chips and the synthetic-data notice', async () => {
    api.listBuyers.mockResolvedValue([
      { id: 3, name: 'Deccan Agro Machines Pvt Ltd', gstin: '36AAFCD5521Q1ZA', synthetic: true,
        profile: profile({ median_days_late: 42.5, pct_paid_late: 100, pct_paid_over_30_late: 70, trend: 'worsening', label: 'Slow' }) },
      { id: 1, name: 'Kaveri Auto Assemblies Pvt Ltd', gstin: '27AABCK7712M1Z9', synthetic: true, profile: profile() },
      { id: 9, name: 'New Buyer Ltd', gstin: null, synthetic: false,
        profile: profile({ invoices_considered: 2, median_days_late: null, pct_paid_late: null, pct_paid_over_30_late: null,
          trend: null, trend_detail: null, label: 'Insufficient history' }) },
    ])
    const { container } = render(<Buyers />)
    expect(await screen.findByText('Deccan Agro Machines Pvt Ltd')).toBeTruthy()
    const slow = container.querySelector('[data-buyer="3"]')
    expect(within(slow).getByText('Slow')).toBeTruthy()
    expect(within(slow).getByText('42.5')).toBeTruthy()
    expect(within(slow).getByText('70%')).toBeTruthy()
    expect(within(slow).getByText('↗︎ worsening')).toBeTruthy() // text glyph, never a colour emoji (B-9)
    const fresh = container.querySelector('[data-buyer="9"]')
    expect(within(fresh).getByText('Insufficient history')).toBeTruthy()
    expect(within(fresh).getAllByText('—').length).toBeGreaterThanOrEqual(3)
    expect(within(fresh).getByText('GSTIN not recorded')).toBeTruthy()
    expect(screen.getByRole('note').textContent).toMatch(/synthetic.*seeded demo data/)
    expect(screen.getAllByText(/Not a credit rating/).length).toBeGreaterThan(0)
    expect(screen.getByText(/minimum 7, from the rule config/)).toBeTruthy() // from /api/health, not hard-coded
  })

  it('shows empty and error states', async () => {
    api.listBuyers.mockResolvedValueOnce([])
    render(<Buyers />)
    expect(await screen.findByText('No buyers yet')).toBeTruthy()
    cleanup()
    api.listBuyers.mockRejectedValueOnce(new Error('Cannot reach the backend at http://localhost:8000.'))
    render(<Buyers />)
    expect(await screen.findByText(/Cannot reach the backend/)).toBeTruthy()
  })
})

const FORECAST = {
  as_of: '2026-11-23', formula: 'expected payment date = due date + buyer median days late …',
  totals: { open: 466944, at_risk: 466944 },
  buckets: [{ key: 'overdue', amount: 444022 }, { key: 'next_30', amount: 22922 }, { key: 'days_31_60', amount: 0 },
    { key: 'beyond_60', amount: 0 }, { key: 'unknown', amount: 0 }],
}

describe('ForecastChart', () => {
  it('draws one bar per bucket in order, values at the tip, hover text and a table view', () => {
    const { container } = render(<ForecastChart forecast={FORECAST} />)
    const rows = [...container.querySelectorAll('[data-bucket]')].map((g) => g.getAttribute('data-bucket'))
    expect(rows).toEqual(['overdue', 'next_30', 'days_31_60', 'beyond_60', 'unknown'])
    expect(container.querySelectorAll('path').length).toBe(2) // zero buckets draw no bar
    expect(screen.getByText('₹4,44,022')).toBeTruthy()
    fireEvent.mouseEnter(container.querySelector('[data-bucket="next_30"]'))
    expect(screen.getByText('Next 30 days: ₹22,922 (5% of open receivables)')).toBeTruthy()
    expect(screen.getByText('How is this calculated?').getAttribute('title')).toMatch(/median days late/)
    fireEvent.click(screen.getByText('Show as table'))
    expect(screen.getAllByText('95%').length).toBe(1)
  })

  it('says so when there is nothing to forecast', () => {
    render(<ForecastChart forecast={{ ...FORECAST, totals: { open: 0 } }} />)
    expect(screen.getByText('No open receivables to forecast.')).toBeTruthy()
  })
})
