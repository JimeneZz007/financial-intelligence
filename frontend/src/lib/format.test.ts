import { describe, expect, it } from 'vitest'

import {
  EMPTY,
  formatByUnit,
  formatChange,
  formatCompact,
  formatCurrency,
  formatCurrencyFull,
  formatMonth,
  formatPercent,
  formatPoints,
  formatSignedCurrency,
  formatSignedCurrencyFull,
  formatSignedPercent,
} from './format'

describe('formatCompact', () => {
  it.each([
    [0, '0'],
    [980, '980'],
    [1284, '1,284'],
    [12_940, '12.9K'],
    [99_940, '99.9K'],
    [345_200, '345K'],
    [999_400, '999K'],
    [999_600, '1.0M'],
    [4_000_000, '4.0M'],
    [59_053_741.75, '59.1M'],
    [1_250_000_000, '1.3B'],
    [-345_200, '-345K'],
  ])('formats %d as %s', (value, expected) => {
    expect(formatCompact(value)).toBe(expected)
  })

  it('keeps the decimal of round millions so figures in a row share their precision', () => {
    expect(formatCurrency(4_000_000)).toBe('$4.0M')
    expect(formatCurrency(3_991_969.68)).toBe('$4.0M')
  })
})

describe('currency', () => {
  it('puts the sign before the symbol', () => {
    expect(formatCurrency(-345_200)).toBe('-$345K')
    expect(formatCurrencyFull(-1234.5)).toBe('-$1,235')
  })

  it('marks the direction of variances explicitly', () => {
    expect(formatSignedCurrency(356_041.75)).toBe('+$356K')
    expect(formatSignedCurrency(-1_124_923)).toBe('-$1.1M')
    expect(formatSignedCurrency(0)).toBe('$0')
    expect(formatSignedCurrencyFull(55_371.4)).toBe('+$55,371')
    expect(formatSignedCurrencyFull(-1118.2)).toBe('-$1,118')
    expect(formatSignedCurrencyFull(0.3)).toBe('$0')
  })
})

describe('ratios', () => {
  it('formats ratios as percentages', () => {
    expect(formatPercent(0.30897)).toBe('30.9%')
    expect(formatPercent(0.30897, 2)).toBe('30.90%')
    expect(formatSignedPercent(0.133522)).toBe('+13.4%')
    expect(formatSignedPercent(-0.183663)).toBe('-18.4%')
  })

  it('does not put a sign on a change that rounds to zero', () => {
    expect(formatSignedPercent(0.0002)).toBe('0.0%')
    expect(formatSignedPercent(-0.0002)).toBe('0.0%')
    expect(formatPoints(-0.0002)).toBe('0.0 pp')
  })

  it('expresses differences between ratios in percentage points', () => {
    expect(formatPoints(-0.013086)).toBe('-1.3 pp')
    expect(formatPoints(0.00137)).toBe('+0.1 pp')
    expect(formatPoints(-0.012745, 2)).toBe('-1.27 pp')
  })
})

describe('missing values', () => {
  it('renders an em dash instead of NaN, null or infinity', () => {
    for (const value of [null, undefined, Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(formatCurrency(value)).toBe(EMPTY)
      expect(formatPercent(value)).toBe(EMPTY)
      expect(formatSignedPercent(value)).toBe(EMPTY)
      expect(formatPoints(value)).toBe(EMPTY)
      expect(formatCompact(value)).toBe(EMPTY)
    }
  })
})

describe('units and changes', () => {
  it('formats a value according to its unit', () => {
    expect(formatByUnit(0.0676, 'percent')).toBe('6.8%')
    expect(formatByUnit(59_053_741, 'currency')).toBe('$59.1M')
    expect(formatByUnit(705_004, 'number')).toBe('705,004')
  })

  it('shows relative change for amounts and percentage points for ratios', () => {
    expect(formatChange(6_956_177, 0.1335, 'currency')).toBe('+13.4%')
    expect(formatChange(-0.0131, null, 'percent')).toBe('-1.3 pp')
  })
})

describe('formatMonth', () => {
  it('supports the three label styles', () => {
    expect(formatMonth('2025-03')).toBe('Mar 2025')
    expect(formatMonth('2025-03', 'short')).toBe('Mar')
    expect(formatMonth('2025-03', 'axis')).toBe('Mar 25')
  })

  it('returns the input when it is not a month', () => {
    expect(formatMonth('nonsense')).toBe('nonsense')
  })
})
