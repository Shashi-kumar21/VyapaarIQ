import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../lib/api.js'
import { splitDraft, splitEmail } from '../lib/drafts.js'
import { parseMarkdown } from '../lib/markdown.js'
import DisputePackPanel from './DisputePackPanel.jsx'
import FollowupsPanel from './FollowupsPanel.jsx'
import ForecastChart from './ForecastChart.jsx'

vi.mock('../lib/api.js', () => ({
  api: { listFollowups: vi.fn(), generateFollowups: vi.fn(), disputePack: vi.fn() },
  blobText: (b) => new Promise((res) => { const r = new FileReader(); r.onload = () => res(r.result); r.readAsText(b) }),
}))

beforeEach(() => vi.resetAllMocks())
afterEach(cleanup)

// Real draft text shape from the backend (app/followups/drafts.py), D-7 for PKG07.
const DRAFT = '[DRAFT - not sent. Review before sending.]\n[VERIFY: the estimated due date 13 Oct 2026 rests on deemed acceptance.]\n' +
  '[Scheduled send date 06 Oct 2026 has passed; kept for reference. Use the latest step instead.]\n\n' +
  'Subject: Upcoming payment: invoice SPC/26-27/0107 due 13 Oct 2026 (estimated)\n\nDear Kaveri Auto Assemblies Pvt Ltd Accounts Team,'
const row = (o) => ({ id: 1, invoice_id: 61, step: -7, step_label: 'D-7', send_on: '2026-10-06', past: true,
  channel: 'email', tone: 'friendly', status: 'draft', draft_text: DRAFT, ...o })

describe('draft helpers', () => {
  it('splits reviewer notes from the message', () => {
    const { notes, body } = splitDraft(DRAFT)
    expect(notes).toHaveLength(3)
    expect(notes[1]).toMatch(/^VERIFY/)
    expect(body.startsWith('Subject: Upcoming payment')).toBe(true)
    expect(body).not.toMatch(/DRAFT|VERIFY/)
  })
})

describe('splitEmail', () => {
  it('separates the subject line from the body', () => {
    expect(splitEmail('Subject: Hello\n\nDear team,\nThanks')).toEqual({ subject: 'Hello', body: 'Dear team,\nThanks' })
    expect(splitEmail('*WhatsApp text*')).toEqual({ subject: null, body: '*WhatsApp text*' })
  })
})

describe('FollowupsPanel', () => {
  it('shows drafts for the chosen tone/channel with notes, badges and copy of the message only', async () => {
    api.listFollowups.mockResolvedValue([row(), row({ id: 2, tone: 'firm', draft_text: '[DRAFT]\n\nFirm text' })])
    const writeText = vi.fn().mockResolvedValue()
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    render(<FollowupsPanel invoiceId={61} />)
    expect(await screen.findByText('D-7')).toBeTruthy()
    expect(screen.getByText('draft, not sent')).toBeTruthy()
    expect(screen.getByText('date passed')).toBeTruthy()
    expect(screen.getByText(/^VERIFY: the estimated due date/).className).toMatch(/amber/)
    fireEvent.click(screen.getByText('Copy subject'))
    await screen.findByText('Copied ✓')
    expect(writeText.mock.calls[0][0]).toBe('Upcoming payment: invoice SPC/26-27/0107 due 13 Oct 2026 (estimated)')
    fireEvent.click(screen.getByText('Copy body'))
    expect(writeText.mock.calls[1][0].startsWith('Dear Kaveri Auto Assemblies')).toBe(true)
    expect(writeText.mock.calls[1][0]).not.toMatch(/Subject:|DRAFT|VERIFY/)
    fireEvent.click(screen.getByRole('radio', { name: 'Firm' }))
    expect(screen.getByText('Firm text')).toBeTruthy()
    fireEvent.click(screen.getByRole('radio', { name: 'WhatsApp' }))
    expect(screen.getByText(/No firm WhatsApp drafts yet/)).toBeTruthy()
  })

  it('generates drafts and shows a 409 clearly', async () => {
    api.listFollowups.mockResolvedValueOnce([]).mockResolvedValueOnce([row()])
    api.generateFollowups.mockResolvedValueOnce({ followups: [] })
    render(<FollowupsPanel invoiceId={61} />)
    fireEvent.click(await screen.findByText('Generate drafts'))
    expect(await screen.findByText('D-7')).toBeTruthy()
    expect(api.generateFollowups).toHaveBeenCalledWith(61, { tone: 'friendly', channel: 'email' })
    api.generateFollowups.mockRejectedValueOnce(new Error('No due date could be determined for this invoice.'))
    fireEvent.click(screen.getByText('Regenerate drafts'))
    expect(await screen.findByText('No due date could be determined for this invoice.')).toBeTruthy()
  })
})

// Real Markdown shape from backend to_markdown (trimmed).
const PACK_MD = [
  '# Evidence pack: invoice SPC/26-27/0107', '',
  '_Prepared 23 Nov 2026 - estimated, not legal advice, verify before use_', '',
  '## Invoice facts', '',
  '| Field | Value |', '|---|---|', '| Invoice no. | SPC/26-27/0107 |', '| Total | [to be verified] |',
  String.raw`| Note | a \| b |`, '',
  '## Summary', '', 'Buyer: Kaveri Auto Assemblies Pvt Ltd.', '', '---',
  '_Generated assistance, not legal advice._', '',
].join('\n')

describe('parseMarkdown', () => {
  it('parses headings, italic lines, tables (with escaped pipes), rules and paragraphs', () => {
    const b = parseMarkdown(PACK_MD)
    expect(b.map((x) => x.type)).toEqual(['h1', 'em', 'h2', 'table', 'h2', 'p', 'hr', 'em'])
    expect(b[3].head).toEqual(['Field', 'Value'])
    expect(b[3].rows).toEqual([['Invoice no.', 'SPC/26-27/0107'], ['Total', '[to be verified]'], ['Note', 'a | b']])
  })
  it('treats markup as text', () => {
    expect(parseMarkdown('<img src=x onerror=alert(1)>')).toEqual([{ type: 'p', text: '<img src=x onerror=alert(1)>' }])
  })
})

describe('DisputePackPanel', () => {
  const md = (text) => ({ blob: new Blob([text]), filename: 'evidence-pack-SPC-26-27-0107.md', format: 'md' })

  it('previews the pack and highlights unverified values', async () => {
    api.disputePack.mockResolvedValue(md(PACK_MD))
    render(<DisputePackPanel invoiceId={61} />)
    expect(await screen.findByText('Evidence pack: invoice SPC/26-27/0107')).toBeTruthy()
    expect(screen.getByText('[to be verified]').className).toMatch(/amber/)
    expect(screen.getByText('Generated assistance, not legal advice.')).toBeTruthy()
    expect(api.disputePack).toHaveBeenCalledWith(61, 'md')
  })

  it('downloads through fetch, reports a PDF fallback, and shows errors instead of raw JSON', async () => {
    api.disputePack.mockResolvedValueOnce(md(PACK_MD))
    URL.createObjectURL = vi.fn(() => 'blob:x')
    URL.revokeObjectURL = vi.fn()
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    render(<DisputePackPanel invoiceId={61} />)
    await screen.findByText('Evidence pack: invoice SPC/26-27/0107')

    api.disputePack.mockResolvedValueOnce({ ...md('x'), format: 'md-fallback' })
    fireEvent.click(screen.getByText('Download PDF'))
    await screen.findByText(/PDF could not be generated/)
    expect(click).toHaveBeenCalledTimes(1)
    expect(api.disputePack).toHaveBeenLastCalledWith(61, 'pdf')

    api.disputePack.mockRejectedValueOnce(new Error('Invoice has not been processed yet.'))
    fireEvent.click(screen.getByText('Download Markdown'))
    await waitFor(() => expect(screen.getByText('Invoice has not been processed yet.')).toBeTruthy())
    expect(click).toHaveBeenCalledTimes(1)
    click.mockRestore()
  })
})

describe('ForecastChart', () => {
  const fc = {
    as_of: '2026-11-23', formula: 'f', totals: { open: 300 },
    buckets: [{ key: 'overdue', amount: 200 }, { key: 'next_30', amount: 100 }],
  }
  afterEach(() => { delete window.matchMedia })

  it('shows the chart on a wide screen, table on demand', () => {
    window.matchMedia = () => ({ matches: false })
    render(<ForecastChart forecast={fc} />)
    expect(screen.getByRole('img')).toBeTruthy()
    expect(screen.queryByRole('table')).toBeNull()
    fireEvent.click(screen.getByText('Show as table'))
    expect(screen.getByRole('table')).toBeTruthy()
  })

  it('starts with the table on a phone, where chart text would be too small', () => {
    window.matchMedia = (q) => ({ matches: q === '(max-width: 639px)' })
    render(<ForecastChart forecast={fc} />)
    expect(screen.getByRole('table')).toBeTruthy()
    expect(screen.getByText('Hide table')).toBeTruthy()
  })
})
