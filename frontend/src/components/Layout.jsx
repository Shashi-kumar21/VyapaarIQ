import { BookOpen, FilePlus2, LayoutDashboard, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router'
import { api } from '../lib/api.js'
import InfoHint from './InfoHint.jsx'

const NAV = [
  { to: '/', label: 'Dashboard', end: true, icon: LayoutDashboard, tool: 'dashboard' },
  { to: '/packages/new', label: 'New package', icon: FilePlus2, tool: 'upload' },
  { to: '/buyers', label: 'Buyers', icon: Users, tool: 'buyers' },
  { to: '/how-it-works', label: 'How it works', icon: BookOpen, tool: 'howItWorks' },
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
    return <span className="font-medium text-red-300" title={state.message}>● Backend unreachable</span>
  }
  return (
    <span className="text-slate-300" title={`extractor ${state.extractor} · today ${state.today}`}>
      <span className="text-emerald-400">●</span> API ok
      <span className="hidden text-[11px] leading-relaxed text-slate-400 lg:mt-1 lg:block">
        extractor <b className="text-slate-200">{state.extractor}</b> · today {state.today}
      </span>
    </span>
  )
}

export default function Layout() {
  return (
    <div className="min-h-screen lg:flex">
      {/* One navigation element: an ink "ledger spine" sidebar on desktop, a top bar on phones.
          Order classes place the status chip top-right on phones and at the bottom on desktop. */}
      <div className="bg-ink lg:w-64 lg:shrink-0">{/* full-height ink column behind the sticky sidebar */}
      <aside className="flex flex-wrap items-center gap-x-3 px-4 pt-3 pb-2 lg:sticky lg:top-0 lg:h-screen lg:flex-col lg:flex-nowrap lg:items-stretch lg:py-6">
        <div className="order-1 flex-1 lg:flex-none lg:px-2">
          <span className="flex items-center gap-2">
            <span aria-hidden="true" className="flex size-8 items-center justify-center rounded-lg bg-accent font-display text-sm font-bold text-white">V</span>
            <span className="font-display text-lg font-bold tracking-tight text-white">VyapaarIQ</span>
          </span>
          <p className="mt-2 hidden text-xs leading-relaxed text-slate-400 lg:block">
            Invoice evidence and payment readiness for MSME suppliers
          </p>
        </div>
        <div className="order-2 text-xs lg:order-4 lg:mt-auto lg:rounded-xl lg:bg-ink-2/70 lg:p-3">
          <BackendStatus />
        </div>
        <nav aria-label="Main" className="order-3 -mx-1 mt-3 flex w-full flex-wrap gap-1 pb-1 lg:mx-0 lg:mt-8 lg:flex-col lg:flex-nowrap">
          {NAV.map((n) => (
            <InfoHint key={n.to} tool={n.tool} side="auto" className="lg:w-full">
              {(t) => (
                <NavLink
                  to={n.to}
                  end={n.end}
                  {...t}
                  className={({ isActive }) =>
                    `flex w-full items-center gap-3 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                      isActive ? 'bg-ink-2 text-white ring-1 ring-inset ring-white/10' : 'text-slate-300 hover:bg-ink-2/60 hover:text-white'}`
                  }
                >
                  <n.icon aria-hidden="true" className="size-4 shrink-0" />{n.label}
                </NavLink>
              )}
            </InfoHint>
          ))}
        </nav>
      </aside>
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* §13 / CLAUDE.md rule 5: always label demo data, illustrative risk, not legal advice. */}
        <div role="note" className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-xs text-amber-900">
          Demo with synthetic data only · risk scores are illustrative, not a prediction of payment ·
          legal figures are estimates, not legal advice — verify before use
        </div>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
