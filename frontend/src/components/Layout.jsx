import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api } from '../lib/api.js'

const NAV = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/packages/new', label: 'New package' },
  { to: '/buyers', label: 'Buyers' },
]

/** Backend reachability + extractor mode, so a dead API is obvious during the demo. */
function BackendStatus() {
  const [state, setState] = useState({ status: 'checking' })
  useEffect(() => {
    let alive = true
    api.health()
      .then((h) => alive && setState({ status: 'ok', ...h }))
      .catch((e) => alive && setState({ status: 'down', message: e.message }))
    return () => {
      alive = false
    }
  }, [])
  if (state.status === 'checking') return <span className="text-slate-400">Checking…</span>
  if (state.status === 'down') {
    return <span className="text-bad font-medium" title={state.message}>● Backend unreachable</span>
  }
  return (
    <span className="text-slate-500" title={`extractor ${state.extractor} · today ${state.today}`}>
      <span className="text-ok">●</span> API ok
      <span className="hidden md:inline"> · extractor <b>{state.extractor}</b> · today {state.today}</span>
    </span>
  )
}

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* §13 / CLAUDE.md rule 5: always label demo data, illustrative risk, not legal advice. */}
      <div role="note" className="bg-amber-100 text-amber-900 text-xs text-center px-4 py-1.5">
        Demo with synthetic data only · risk scores are illustrative, not a prediction of payment ·
        legal figures are estimates, not legal advice — verify before use
      </div>
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-4 py-2 sm:h-14 flex flex-wrap items-center gap-x-6 gap-y-1">
          <span className="font-semibold text-lg tracking-tight">VyapaarIQ</span>
          <nav className="flex gap-1 text-sm order-3 sm:order-none w-full sm:w-auto">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-md ${isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'}`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
          {/* Visible at every width (compact on phones); a dead API must be obvious in the demo. */}
          <div className="ml-auto text-xs"><BackendStatus /></div>
        </div>
      </header>
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
