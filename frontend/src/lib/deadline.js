import { date } from './format.js'

/**
 * Deadline text for an action (B-8). The backend clamps an action's target date to today when
 * the invoice due date (minus the lead time) has already passed, so "due by <today>" hid that
 * the payment is already late. When the invoice due date is before the action date, say so.
 */
export function deadlineText(dueBy, invoiceDue) {
  if (!dueBy) return 'no date'
  if (invoiceDue && invoiceDue < dueBy) return `act now · payment overdue since ${date(invoiceDue)}`
  return `due by ${date(dueBy)}`
}
