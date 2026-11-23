import { useEffect, useState } from 'react'

function matches(query) {
  try {
    return window.matchMedia(query).matches
  } catch {
    return false // no matchMedia (jsdom, very old browsers): treat as a wide screen
  }
}

/** True while the CSS media query matches; follows resizes and rotation. */
export function useMediaQuery(query) {
  const [on, setOn] = useState(() => matches(query))
  useEffect(() => {
    let mql
    try {
      mql = window.matchMedia(query)
    } catch {
      return undefined
    }
    const update = () => setOn(mql.matches)
    update()
    mql.addEventListener?.('change', update)
    return () => mql.removeEventListener?.('change', update)
  }, [query])
  return on
}

/** Tailwind's `sm` breakpoint is 640px: below it counts as a phone. */
export const PHONE = '(max-width: 639px)'
