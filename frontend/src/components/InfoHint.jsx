import { ArrowUpRight, Info } from 'lucide-react'
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { placeCard } from '../lib/placement.js'
import { TOOLS } from '../lib/tools.js'

// Hover card that explains a tool, adapted from Watermelon UI "Tooltip 11" (hover card with a
// short description and a Learn more link) to our JS + Tailwind code without extra dependencies.
// Opens on hover and on keyboard focus, toggles on tap, closes on Escape, on scroll, when focus
// leaves, or when another card opens. The card is position: fixed and placed by placeCard(), so it
// is always fully inside the viewport (phones included) and never clipped by a scrolling parent.
// Two modes:
//   <InfoHint tool="checks" />                                    -> a small (i) button as the trigger
//   <InfoHint tool="checks">{(t) => <button {...t}/>}</InfoHint>  -> any element as the trigger

const OPEN_DELAY = 120
const CLOSE_DELAY = 150
const OPEN_EVENT = 'infohint:open'

export default function InfoHint({ tool, side = 'bottom', align = 'start', children, className = '' }) {
  const info = typeof tool === 'string' ? TOOLS[tool] : tool
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState(null)
  const timer = useRef(null)
  const wrapRef = useRef(null)
  const cardRef = useRef(null)
  const id = useId()

  useEffect(() => () => clearTimeout(timer.current), [])

  // only one card at a time; scrolling or resizing closes it (it would no longer sit by its trigger)
  useEffect(() => {
    if (!open) return undefined
    window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: id }))
    const onOther = (e) => e.detail !== id && setOpen(false)
    const close = () => setOpen(false)
    window.addEventListener(OPEN_EVENT, onOther)
    window.addEventListener('scroll', close, true)
    window.addEventListener('resize', close)
    return () => {
      window.removeEventListener(OPEN_EVENT, onOther)
      window.removeEventListener('scroll', close, true)
      window.removeEventListener('resize', close)
    }
  }, [open, id])

  useLayoutEffect(() => {
    if (!open) {
      setPos(null)
      return
    }
    const trigger = wrapRef.current?.firstElementChild?.getBoundingClientRect?.()
    const card = cardRef.current?.getBoundingClientRect?.()
    if (!trigger || !card) return
    setPos(placeCard(trigger, card, { width: window.innerWidth, height: window.innerHeight }, side, align))
  }, [open, side, align])

  if (!info) return children ? children({}) : null

  const later = (value, ms) => {
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setOpen(value), ms)
  }
  const show = () => later(true, OPEN_DELAY)
  const hide = () => later(false, CLOSE_DELAY)
  const onKeyDown = (e) => {
    if (e.key === 'Escape' && open) {
      e.stopPropagation()
      clearTimeout(timer.current)
      setOpen(false)
    }
  }
  // focus moving into the card (its Learn more link) keeps it open
  const onBlur = (e) => {
    if (!e.currentTarget.contains(e.relatedTarget)) hide()
  }

  const triggerProps = {
    onMouseEnter: show,
    onMouseLeave: hide,
    onFocus: show,
    'aria-describedby': open ? id : undefined,
  }

  return (
    <span ref={wrapRef} className={`relative inline-flex ${className}`} onKeyDown={onKeyDown} onBlur={onBlur}>
      {children ? children(triggerProps) : (
        <button
          type="button"
          {...triggerProps}
          onClick={() => { clearTimeout(timer.current); setOpen((o) => !o) }}
          aria-label={`About ${info.title}`}
          aria-expanded={open}
          className="inline-flex size-5 items-center justify-center rounded-full text-muted hover:bg-accent-soft hover:text-accent focus-visible:outline-2 focus-visible:outline-accent"
        >
          <Info aria-hidden="true" className="size-3.5" />
        </button>
      )}
      {open && (
        <div
          ref={cardRef}
          id={id}
          role="group"
          aria-label={info.title}
          onMouseEnter={() => clearTimeout(timer.current)}
          onMouseLeave={hide}
          data-infohint={typeof tool === 'string' ? tool : undefined}
          style={pos ? { left: pos.left, top: pos.top } : { left: 0, top: 0, visibility: 'hidden' }}
          className="fixed z-50 w-72 max-w-[calc(100vw-2rem)] rounded-xl border border-line bg-surface p-4 text-left font-normal normal-case tracking-normal shadow-pop"
        >
          <p className="font-display text-sm font-semibold text-ink">{info.title}</p>
          <p className="mt-1 text-xs leading-relaxed text-muted">{info.summary}</p>
          {info.points?.length > 0 && (
            <ul className="mt-2 space-y-1 text-xs text-ink/80">
              {info.points.map((p) => (
                <li key={p} className="flex gap-2"><span aria-hidden="true" className="mt-1.5 size-1 shrink-0 rounded-full bg-accent" />{p}</li>
              ))}
            </ul>
          )}
          {info.anchor && (
            <Link
              to={`/how-it-works#${info.anchor}`}
              className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline"
            >
              Learn more <ArrowUpRight aria-hidden="true" className="size-3.5" />
            </Link>
          )}
        </div>
      )}
    </span>
  )
}
