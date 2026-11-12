import { describe, expect, it } from 'vitest'

import { dimensions } from '@/test/fixtures'

import { buildPresets, resolveFilters } from './filters'

const presets = buildPresets(dimensions.period.months, dimensions.period.fiscal_years)
const resolve = (query: string) => resolveFilters(new URLSearchParams(query), dimensions, presets)

describe('buildPresets', () => {
  it('lists fiscal years newest first, then rolling windows, then all time', () => {
    expect(presets.map((preset) => preset.id)).toEqual(['fy2025', 'fy2024', 'fy2023', 'last12', 'last6', 'last3', 'all'])
    expect(presets[0]).toMatchObject({ label: 'FY 2025', start: '2025-01', end: '2025-12' })
    expect(presets.find((preset) => preset.id === 'last3')).toMatchObject({ start: '2025-10', end: '2025-12' })
    expect(presets.at(-1)).toMatchObject({ start: '2023-01', end: '2025-12' })
  })

  it('offers a fiscal year only when all of its months have data', () => {
    const partial = buildPresets(['2024-11', '2024-12', '2025-01', '2025-02'], [2024, 2025])
    expect(partial.map((preset) => preset.id)).toEqual(['last3', 'all'])
  })

  it('returns nothing for an empty period', () => {
    expect(buildPresets([], [])).toEqual([])
  })
})

describe('resolveFilters', () => {
  it('defaults to the latest fiscal year, every unit and the prior-year comparison', () => {
    expect(resolve('')).toEqual({ start: '2025-01', end: '2025-12', units: [], compare: 'previous_year' })
  })

  it('reads a valid selection from the URL', () => {
    expect(resolve('from=2024-04&to=2024-06&bu=WHS,RET&cmp=pp')).toEqual({
      start: '2024-04',
      end: '2024-06',
      // Units come back in catalogue order, whatever the order in the URL.
      units: ['RET', 'WHS'],
      compare: 'previous_period',
    })
  })

  it.each([
    ['months outside the data', 'from=2019-01&to=2019-12'],
    ['an inverted range', 'from=2025-06&to=2025-01'],
    ['a malformed month', 'from=2025-1&to=2025-12'],
    ['half a range', 'from=2025-03'],
  ])('falls back to the default period for %s', (_, query) => {
    expect(resolve(query)).toMatchObject({ start: '2025-01', end: '2025-12' })
  })

  it('drops unknown unit codes and treats "all units" as no filter', () => {
    expect(resolve('bu=RET,XXX').units).toEqual(['RET'])
    expect(resolve('bu=RET,ECM,WHS,COR').units).toEqual([])
    expect(resolve('cmp=unknown').compare).toBe('previous_year')
  })
})
