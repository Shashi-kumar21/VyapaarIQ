// Small shared UI pieces: loading / error / empty states, chips, cards.

export function Loading({ label = 'Loading…' }) {
  return (
    <div role="status" className="text-sm text-slate-500 py-8 text-center animate-pulse">{label}</div>
  )
}

export function ErrorBox({ error, onRetry }) {
  return (
    <div role="alert" className="border border-red-200 bg-red-50 text-red-800 rounded-lg p-4 text-sm">
      <p className="font-medium">Something went wrong</p>
      <p className="mt-1">{error?.message || String(error)}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="mt-3 px-3 py-1.5 rounded-md bg-red-700 text-white">
          Try again
        </button>
      )}
    </div>
  )
}

export function Empty({ title, children }) {
  return (
    <div className="border border-dashed border-slate-300 rounded-lg p-8 text-center text-sm text-slate-500">
      <p className="font-medium text-slate-700">{title}</p>
      {children && <div className="mt-2">{children}</div>}
    </div>
  )
}

export function Card({ title, aside, children, className = '' }) {
  return (
    <section className={`bg-white border border-slate-200 rounded-xl p-4 ${className}`}>
      {(title || aside) && (
        <div className="flex items-baseline justify-between gap-2 mb-3">
          {title && <h2 className="font-semibold">{title}</h2>}
          {aside && <div className="text-xs text-slate-500">{aside}</div>}
        </div>
      )}
      {children}
    </section>
  )
}

export function Stat({ label, value, hint, tone = 'default', title }) {
  const tones = { default: 'text-slate-900', bad: 'text-bad', warn: 'text-warn', ok: 'text-ok' }
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4" title={title}>
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`text-2xl font-semibold mt-1 ${tones[tone]}`}>{value}</div>
      {hint && <div className="text-xs text-slate-500 mt-1">{hint}</div>}
    </div>
  )
}

const TIER_STYLE = {
  Low: 'bg-green-100 text-green-800',
  Medium: 'bg-amber-100 text-amber-900',
  High: 'bg-red-100 text-red-800',
}

export function TierBadge({ tier }) {
  if (!tier) return <span className="text-slate-400">—</span>
  return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${TIER_STYLE[tier] || ''}`}>{tier}</span>
}

const SEVERITY_STYLE = {
  blocker: 'bg-red-100 text-red-800',
  warning: 'bg-amber-100 text-amber-900',
  info: 'bg-slate-100 text-slate-700',
}

export function SeverityChip({ severity }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${SEVERITY_STYLE[severity] || SEVERITY_STYLE.info}`}>
      {severity}
    </span>
  )
}
