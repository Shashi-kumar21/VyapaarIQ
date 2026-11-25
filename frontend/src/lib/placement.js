// Where to put a hover card so it is always fully on screen (QA #31: absolute cards anchored to
// the trigger ran up to 231 px off a 375 px phone). Pure function, unit-tested.

export const GAP = 8 // between trigger and card
export const MARGIN = 16 // minimum distance from the viewport edge

/**
 * @param trigger  DOMRect-like {left, right, top, bottom} of the trigger (viewport coordinates)
 * @param card     {width, height} of the card
 * @param view     {width, height} of the viewport
 * @param side     'bottom' | 'top' | 'right' | 'auto' (right of the trigger on wide screens, else below)
 * @param align    'start' | 'end' | 'center' (for bottom/top)
 * @returns {left, top} for a position: fixed card, clamped inside the viewport margins
 */
export function placeCard(trigger, card, view, side = 'bottom', align = 'start', wide = 1024) {
  const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), Math.max(lo, hi))
  let s = side === 'auto' ? (view.width >= wide ? 'right' : 'bottom') : side
  let left
  let top
  if (s === 'right') {
    left = trigger.right + GAP + 4
    top = trigger.top
    if (left + card.width > view.width - MARGIN) s = 'bottom' // no room on the right: go below
  }
  if (s === 'bottom' || s === 'top') {
    const width = trigger.right - trigger.left
    left = align === 'end' ? trigger.right - card.width
      : align === 'center' ? trigger.left + width / 2 - card.width / 2
        : trigger.left
    const below = trigger.bottom + GAP
    const above = trigger.top - GAP - card.height
    const fitsBelow = below + card.height <= view.height - MARGIN
    const fitsAbove = above >= MARGIN
    top = s === 'top' ? (fitsAbove || !fitsBelow ? above : below) : (fitsBelow || !fitsAbove ? below : above)
  }
  return {
    left: clamp(left, MARGIN, view.width - MARGIN - card.width),
    top: clamp(top, MARGIN, view.height - MARGIN - card.height),
  }
}
