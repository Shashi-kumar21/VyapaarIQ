import { AlertTriangle, CheckCircle2, CircleDashed, Info, Loader2, OctagonAlert } from 'lucide-react'
import InfoHint from './InfoHint.jsx'

// Shared UI pieces (design tokens in index.css, D-43): page header, cards, stat tiles,
// loading / error / empty states, buttons and status chips.

export function PageHeader({ eyebrow, title, tool, children, actions }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0 max-w-3xl">
        {eyebrow && <p className="text-xs font-semibold uppercase tracking-[0.14em] text-accent">{eyebrow}</p>}
        <div className="mt-1 flex items-center gap-2">
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink sm:text-3xl">{title}</h1>
          {tool && <InfoHint tool={tool} />}
        </div>
        {children && <div className="mt-2 text-sm leading-relaxed text-muted">{children}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </header>
  )
}

export function Loading({ label = 'Loading…' }) {
  return (
    <div role="status" className="flex items-center justify-center gap-2 py-16 text-sm text-muted">
      <Loader2 aria-hidden="true" className="size-4 animate-spin" />{label}
    </div>
  )
}

export function ErrorBox({ error, onRetry }) {
  return (
    <div role="alert" className="flex gap-3 rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-900">
      <OctagonAlert aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-bad" />
      <div>
        <p className="font-semibold">Something went wrong</p>
        <p className="mt-1">{error?.message || String(error)}</p>
        {onRetry && (
          <button type="button" onClick={onRetry} className="mt-3 rounded-lg bg-bad px-3 py-1.5 font-medium text-white hover:bg-bad/90">
            Try again
          </button>
        )}
      </div>
    </div>
  )
}

export function Empty({ title, children, icon: Icon = CircleDashed, action }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-line bg-surface px-6 py-12 text-center">
      <span className="flex size-12 items-center justify-center rounded-full bg-accent-soft text-accent">
        <Icon aria-hidden="true" className="size-6" />
      </span>
      <p className="mt-4 font-display font-semibold text-ink">{title}</p>
      {children && <div className="mt-1 max-w-md text-sm text-muted">{children}</div>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function Card({ title, aside, tool, children, className = '' }) {
  return (
    <section className={`rounded-2xl border border-line bg-surface p-5 shadow-card ${className}`}>
      {(title || aside) && (
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
          {title && (
            <div className="flex items-center gap-1.5">
              <h2 className="font-display font-semibold text-ink">{title}</h2>
              {tool && <InfoHint tool={tool} />}
            </div>
          )}
          {aside && <div className="text-xs text-muted">{aside}</div>}
        </div>
      )}
      {children}
    </section>
  )
}

const STAT_TONE = {
  default: { value: 'text-ink', icon: 'bg-accent-soft text-accent' },
  bad: { value: 'text-bad', icon: 'bg-red-50 text-bad' },
  warn: { value: 'text-warn', icon: 'bg-amber-50 text-warn' },
  ok: { value: 'text-ok', icon: 'bg-green-50 text-ok' },
}

/** KPI tile, after Watermelon "Stats 2": icon pill, label with an info card, big tabular figure. */
export function Stat({ label, value, hint, tone = 'default', title, icon: Icon, tool }) {
  const t = STAT_TONE[tone] || STAT_TONE.default
  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-card" title={title}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1">
          <span className="text-xs font-medium uppercase leading-tight tracking-wide text-muted">{label}</span>
          {tool && <InfoHint tool={tool} />}
        </div>
        {Icon && (
          <span className={`flex size-8 shrink-0 items-center justify-center rounded-lg ${t.icon}`}>
            <Icon aria-hidden="true" className="size-4" />
          </span>
        )}
      </div>
      <div className={`mt-2 font-display text-2xl font-bold tabular-nums tracking-tight ${t.value}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  )
}

const TIER_STYLE = {
  Low: { cls: 'bg-green-50 text-green-800 ring-green-600/20', dot: 'bg-ok' },
  Medium: { cls: 'bg-amber-50 text-amber-900 ring-amber-600/20', dot: 'bg-warn' },
  High: { cls: 'bg-red-50 text-red-800 ring-red-600/20', dot: 'bg-bad' },
}

export function TierBadge({ tier }) {
  if (!tier) return <span className="text-muted">—</span>
  const s = TIER_STYLE[tier] || { cls: 'bg-paper text-muted ring-line', dot: 'bg-muted' }
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${s.cls}`}>
      <span aria-hidden="true" className={`size-1.5 rounded-full ${s.dot}`} />{tier}
    </span>
  )
}

const SEVERITY_STYLE = {
  blocker: { cls: 'bg-red-50 text-red-800 ring-red-600/20', Icon: OctagonAlert },
  warning: { cls: 'bg-amber-50 text-amber-900 ring-amber-600/20', Icon: AlertTriangle },
  info: { cls: 'bg-paper text-muted ring-line', Icon: Info },
}

export function SeverityChip({ severity }) {
  const s = SEVERITY_STYLE[severity] || SEVERITY_STYLE.info
  return (
    <span className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${s.cls}`}>
      <s.Icon aria-hidden="true" className="size-3" />{severity}
    </span>
  )
}

const STATUS_STYLE = {
  pass: { cls: 'bg-green-50 text-green-800 ring-green-600/20', Icon: CheckCircle2 },
  fail: { cls: 'bg-red-50 text-red-800 ring-red-600/20', Icon: OctagonAlert },
  missing: { cls: 'bg-red-50 text-red-800 ring-red-600/20', Icon: CircleDashed },
  uncertain: { cls: 'bg-amber-50 text-amber-900 ring-amber-600/20', Icon: AlertTriangle },
  skipped: { cls: 'bg-paper text-muted ring-line', Icon: CircleDashed },
}

export function StatusChip({ status }) {
  const s = STATUS_STYLE[status] || STATUS_STYLE.skipped
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${s.cls}`}>
      <s.Icon aria-hidden="true" className="size-3" />{status}
    </span>
  )
}
