import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../lib/api.js'
import { TOOLS, TOOL_ORDER } from '../lib/tools.js'
import HowItWorks from '../pages/HowItWorks.jsx'
import InfoHint from './InfoHint.jsx'
import Layout from './Layout.jsx'

vi.mock('../lib/api.js', () => ({ api: { health: vi.fn() } }))

beforeEach(() => {
  vi.useFakeTimers()
  api.health.mockResolvedValue({ status: 'ok', extractor: 'fixture', today: '2026-11-23' })
})
afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

const wrap = (ui, path = '/') => render(<MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>)
const tick = () => act(() => { vi.advanceTimersByTime(300) })

describe('InfoHint (hover card for a tool, after Watermelon Tooltip 11)', () => {
  it('opens on hover with the tool summary, its key points and a Learn more link', () => {
    wrap(<InfoHint tool="checks" />)
    const trigger = screen.getByRole('button', { name: 'About Checks' })
    expect(screen.queryByRole('group')).toBeNull()
    fireEvent.mouseEnter(trigger)
    tick()
    const card = screen.getByRole('group', { name: 'Checks' })
    expect(card.textContent).toContain(TOOLS.checks.summary)
    expect(card.textContent).toContain(TOOLS.checks.points[0])
    expect(screen.getByRole('link', { name: /Learn more/ }).getAttribute('href')).toBe('/how-it-works#step-checks')
    expect(trigger.getAttribute('aria-describedby')).toBe(card.id)
    fireEvent.mouseLeave(trigger)
    tick()
    expect(screen.queryByRole('group')).toBeNull()
  })

  it('opens on keyboard focus, stays open while focus moves into the card, closes on Escape', () => {
    wrap(<InfoHint tool="interest" />)
    const trigger = screen.getByRole('button', { name: 'About Statutory interest' })
    fireEvent.focus(trigger)
    tick()
    const link = screen.getByRole('link', { name: /Learn more/ })
    fireEvent.blur(trigger, { relatedTarget: link })
    tick()
    expect(screen.getByRole('group', { name: 'Statutory interest' })).toBeTruthy()
    fireEvent.keyDown(link, { key: 'Escape' })
    expect(screen.queryByRole('group')).toBeNull()
  })

  it('toggles on tap (touch screens have no hover)', () => {
    wrap(<InfoHint tool="buyers" />)
    const trigger = screen.getByRole('button', { name: 'About Buyer reliability' })
    fireEvent.click(trigger)
    expect(trigger.getAttribute('aria-expanded')).toBe('true')
    expect(screen.getByRole('group', { name: 'Buyer reliability' })).toBeTruthy()
    fireEvent.click(trigger)
    expect(screen.queryByRole('group')).toBeNull()
  })

  it('can use any element as the trigger (navigation links, tabs)', () => {
    wrap(<InfoHint tool="dashboard">{(t) => <a href="/x" {...t}>Dashboard</a>}</InfoHint>)
    fireEvent.mouseEnter(screen.getByText('Dashboard'))
    tick()
    expect(screen.getByRole('group', { name: 'Dashboard' })).toBeTruthy()
  })
})

describe('Layout navigation', () => {
  it('has a How it works entry, and every nav item explains itself on hover', async () => {
    wrap(<Routes><Route element={<Layout />}><Route index element={<p>home</p>} /></Route></Routes>)
    await act(async () => { await Promise.resolve() })
    expect(screen.getByText(/API ok/)).toBeTruthy()
    for (const [label, tool] of [['Dashboard', 'dashboard'], ['New package', 'upload'], ['Buyers', 'buyers'], ['How it works', 'howItWorks']]) {
      const link = screen.getByRole('link', { name: label })
      fireEvent.mouseEnter(link)
      tick()
      expect(screen.getByRole('group', { name: TOOLS[tool].title })).toBeTruthy()
      fireEvent.mouseLeave(link)
      tick()
    }
    expect(screen.getByRole('link', { name: 'How it works' }).getAttribute('href')).toBe('/how-it-works')
    expect(screen.getByRole('note').textContent).toMatch(/synthetic data only/) // rule 5 banner kept
  })
})

describe('How it works page', () => {
  it('shows the flow, the 14 checks, the law, every tool and a glossary', () => {
    wrap(<HowItWorks />, '/how-it-works')
    expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/claim you can prove/)
    expect(screen.getAllByRole('listitem').length).toBeGreaterThan(5)
    for (const id of ['C01', 'C10', 'C14']) expect(screen.getByText(id)).toBeTruthy()
    expect(screen.getByText('P × (1 + r/12)^m × (1 + r/12 × d/30) − P')).toBeTruthy()
    for (const key of TOOL_ORDER) expect(screen.getByRole('heading', { name: TOOLS[key].title, level: 3 })).toBeTruthy()
    expect(screen.getByText('Deemed acceptance')).toBeTruthy()
  })

  it('has a section for every Learn more link, so no hover card points nowhere', () => {
    const { container } = wrap(<HowItWorks />, '/how-it-works')
    for (const [key, t] of Object.entries(TOOLS)) {
      expect(container.querySelector(`[id="${t.anchor}"]`), `${key} -> #${t.anchor}`).not.toBeNull()
    }
  })

  it('scrolls to the section named in the address', () => {
    const spy = vi.fn()
    Element.prototype.scrollIntoView = spy
    wrap(<HowItWorks />, '/how-it-works#tool-forecast')
    expect(spy).toHaveBeenCalled()
    expect(spy.mock.contexts[0].id).toBe('tool-forecast')
    delete Element.prototype.scrollIntoView
  })
})
