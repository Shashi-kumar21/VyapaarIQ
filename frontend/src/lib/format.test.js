import { describe, expect, it } from 'vitest'
import { date, inr, pct, roundHalfEven } from './format.js'

describe('inr', () => {
  it('uses Indian grouping (matches backend app/fmt.py)', () => {
    expect(inr(240000)).toBe('₹2,40,000')
    expect(inr(12345678.4)).toBe('₹1,23,45,678')
    expect(inr(22921.5)).toBe('₹22,922')
    expect(inr(999)).toBe('₹999')
    expect(inr(-1500)).toBe('-₹1,500')
    expect(inr(399480, { paise: true })).toBe('₹3,99,480.00')
  })
  it('rounds exact halves to even like the backend', () => {
    expect(inr(22922.5)).toBe('₹22,922')
    expect(inr(22923.5)).toBe('₹22,924')
    expect(inr(0.125, { paise: true })).toBe('₹0.12')
    expect(roundHalfEven(2.5)).toBe(2)
    expect(roundHalfEven(3.5)).toBe(4)
    expect(roundHalfEven(2.6)).toBe(3)
  })
  it('shows a dash for unknown amounts', () => {
    expect(inr(null)).toBe('—')
    expect(inr(undefined)).toBe('—')
  })
})

describe('date and pct', () => {
  it('formats ISO dates without time-zone shifts', () => {
    expect(date('2026-10-13')).toBe('13 Oct 2026')
    expect(date('2026-11-23T11:23:21+00:00')).toBe('23 Nov 2026')
    expect(date(null)).toBe('—')
  })
  it('formats fractions', () => {
    expect(pct(0.84)).toBe('84%')
    expect(pct(null)).toBe('—')
  })
})
