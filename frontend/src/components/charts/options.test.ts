import { describe, expect, it } from 'vitest'

import { chartColors } from '@/lib/chart-theme'

import { evolutionOption, signedColumnsOption, stackedColumnsOption, waterfallBars, waterfallOption } from './options'

type Series = { name?: string; type: string; data: unknown[]; stack?: string; barMaxWidth?: number }
const seriesOf = (option: unknown) => (option as { series: Series[] }).series

describe('waterfallBars', () => {
  it('stands totals on zero and floats effects from the running level', () => {
    const bars = waterfallBars([
      { label: 'Budget', kind: 'total', amount: 100 },
      { label: 'Revenue', kind: 'effect', amount: 30 },
      { label: 'Costs', kind: 'effect', amount: -50 },
      { label: 'Actual', kind: 'total', amount: 80 },
    ])
    expect(bars.map((bar) => [bar.start, bar.end])).toEqual([
      [0, 100],
      [100, 130],
      [130, 80],
      [0, 80],
    ])
  })

  it('lands exactly on the closing total when the effects add up', () => {
    const steps = [
      { label: 'Start', kind: 'total' as const, amount: 3_450_381.95 },
      { label: 'Revenue', kind: 'effect' as const, amount: 6_956_177.61 },
      { label: 'Costs', kind: 'effect' as const, amount: -6_414_589.88 },
      { label: 'End', kind: 'total' as const, amount: 3_991_969.68 },
    ]
    const bars = waterfallBars(steps)
    expect(bars[2]!.end).toBeCloseTo(steps[3]!.amount, 2)
  })
})

describe('waterfallOption', () => {
  it('draws bars above, below and across zero from stacked parts', () => {
    const option = waterfallOption([
      { label: 'Start', kind: 'total', amount: 50 },
      { label: 'Loss', kind: 'effect', amount: -80 }, // crosses zero: 50 -> -30
      { label: 'More loss', kind: 'effect', amount: -20 }, // entirely below: -30 -> -50
      { label: 'Recovery', kind: 'effect', amount: 70 }, // crosses back: -50 -> 20
      { label: 'End', kind: 'total', amount: 20 },
    ])
    const [offset, above, below] = seriesOf(option)
    const values = (series: Series | undefined) =>
      series!.data.map((item) => (typeof item === 'object' && item !== null ? (item as { value: unknown }).value : item))
    expect(values(offset)).toEqual([0, 0, -30, 0, 0])
    expect(values(above)).toEqual([50, 50, '-', 20, 20])
    expect(values(below)).toEqual(['-', -30, -20, -50, '-'])
  })

  it('colours totals as data and effects by their sign', () => {
    const option = waterfallOption([
      { label: 'Start', kind: 'total', amount: 10 },
      { label: 'Up', kind: 'effect', amount: 5 },
      { label: 'Down', kind: 'effect', amount: -3 },
    ])
    const colors = seriesOf(option)[1]!.data.map((item) => (item as { itemStyle: { color: string } }).itemStyle.color)
    expect(colors).toEqual([chartColors.series, chartColors.favorable, chartColors.unfavorable])
  })
})

describe('evolutionOption', () => {
  const points = [
    { month: '2025-01', actual: 100, budget: 110 },
    { month: '2025-02', actual: 120, budget: 115 },
  ]

  it('plots actuals as columns and the budget as a line on a single axis', () => {
    const option = evolutionOption(points, 'currency', { actual: 'Actual', budget: 'Budget' })
    const series = seriesOf(option)
    expect(series.map((item) => [item.name, item.type])).toEqual([
      ['Actual', 'bar'],
      ['Budget', 'line'],
    ])
    expect(series[0]!.barMaxWidth).toBeLessThanOrEqual(24)
    expect((option as { yAxis: unknown }).yAxis).not.toBeInstanceOf(Array)
  })

  it('adds the comparison line only when comparison data exists', () => {
    const labels = { actual: 'Actual', budget: 'Budget', comparison: 'Prior year' }
    expect(seriesOf(evolutionOption(points, 'currency', labels))).toHaveLength(2)
    const withComparison = points.map((point) => ({ ...point, comparison: 90 }))
    expect(seriesOf(evolutionOption(withComparison, 'currency', labels))).toHaveLength(3)
  })
})

describe('stackedColumnsOption', () => {
  it('keeps series in the given order so colour follows the entity, not its rank', () => {
    const option = stackedColumnsOption(
      ['2025-01'],
      [
        { key: 'RET', label: 'Retail Stores', color: '#111111', values: [5] },
        { key: 'ECM', label: 'E-commerce', color: '#222222', values: [50] },
      ],
    )
    const series = seriesOf(option)
    expect(series.map((item) => item.name)).toEqual(['Retail Stores', 'E-commerce'])
    expect(new Set(series.map((item) => item.stack)).size).toBe(1)
  })
})

describe('signedColumnsOption', () => {
  it('colours each column by favourability, not by the sign of the number', () => {
    const option = signedColumnsOption([
      { label: 'Jan', value: 100, favorable: true },
      { label: 'Feb', value: 100, favorable: false }, // a cost overrun is positive and unfavorable
      { label: 'Mar', value: 1, favorable: null },
    ])
    const colors = seriesOf(option)[0]!.data.map((item) => (item as { itemStyle: { color: string } }).itemStyle.color)
    expect(colors).toEqual([chartColors.favorable, chartColors.unfavorable, chartColors.neutral])
  })
})
