/**
 * ECharts option builders. Each returns a plain option object from already-fetched data,
 * so they are easy to unit test and the components stay declarative.
 *
 * Mark specs follow docs/UI_DESIGN.md: columns capped at 24px with a 4px rounded data end,
 * 2px lines, solid hairline grid, a 2px surface gap between stacked segments.
 */
import type { EChartsCoreOption } from 'echarts/core'

import {
  baseOption,
  categoryAxis,
  chartColors,
  tooltipHtml,
  valueAxis,
  type TooltipRow,
} from '@/lib/chart-theme'
import {
  formatByUnit,
  formatCurrency,
  formatMonth,
  formatPercent,
  formatSignedCurrency,
  type Unit,
} from '@/lib/format'

const BAR_MAX_WIDTH = 24
const LINE_WIDTH = 2

interface AxisParam {
  dataIndex: number
}

const axisFormatter = (unit: Unit) => (value: number) =>
  unit === 'percent' ? formatPercent(value, 0) : formatCurrency(value, 1)

const monthAxis = (months: string[]) =>
  categoryAxis(months.map((m) => formatMonth(m, months.length > 12 ? 'axis' : 'short')))

const lineSeries = (name: string, color: string, data: (number | null)[], extra: object = {}) => ({
  name,
  type: 'line' as const,
  data,
  symbol: 'circle',
  symbolSize: 8,
  showSymbol: data.length <= 12,
  lineStyle: { color, width: LINE_WIDTH, cap: 'round' as const, join: 'round' as const },
  itemStyle: { color, borderColor: chartColors.surface, borderWidth: 2 },
  emphasis: { focus: 'none' as const },
  ...extra,
})

// --------------------------------------------------------------------------- //
// Actual vs budget vs comparison over time
// --------------------------------------------------------------------------- //
export interface EvolutionPoint {
  month: string
  actual: number | null
  budget: number | null
  comparison?: number | null
  /** Extra line shown at the bottom of the tooltip (for example year-over-year growth). */
  note?: string
}

export function evolutionOption(
  points: EvolutionPoint[],
  unit: Unit,
  labels: { actual: string; budget: string; comparison?: string },
): EChartsCoreOption {
  const months = points.map((p) => p.month)
  const hasComparison = Boolean(labels.comparison) && points.some((p) => p.comparison != null)
  return {
    ...baseOption,
    tooltip: {
      ...(baseOption.tooltip as object),
      formatter: (params: AxisParam[]) => {
        const point = points[params[0]?.dataIndex ?? 0]
        if (!point) return ''
        const rows: TooltipRow[] = [
          { label: labels.actual, value: formatByUnit(point.actual, unit), color: chartColors.series, mark: 'bar' },
          { label: labels.budget, value: formatByUnit(point.budget, unit), color: chartColors.budget, muted: true },
        ]
        if (hasComparison && labels.comparison) {
          rows.push({
            label: labels.comparison,
            value: formatByUnit(point.comparison, unit),
            color: chartColors.comparison,
            muted: true,
          })
        }
        const gap =
          point.actual != null && point.budget != null
            ? unit === 'percent'
              ? `${((point.actual - point.budget) * 100).toFixed(1)} pp vs budget`
              : `${formatSignedCurrency(point.actual - point.budget)} vs budget`
            : undefined
        const footer = [gap, point.note].filter(Boolean).join(' · ')
        return tooltipHtml(formatMonth(point.month), rows, footer || undefined)
      },
    },
    xAxis: monthAxis(months),
    yAxis: valueAxis(axisFormatter(unit)),
    series: [
      {
        name: labels.actual,
        type: 'bar',
        data: points.map((p) => p.actual),
        barMaxWidth: BAR_MAX_WIDTH,
        itemStyle: { color: chartColors.series, borderRadius: [4, 4, 0, 0] },
        emphasis: { itemStyle: { color: '#5b9cec' } },
      },
      lineSeries(
        labels.budget,
        chartColors.budget,
        points.map((p) => p.budget),
      ),
      ...(hasComparison && labels.comparison
        ? [
            lineSeries(
              labels.comparison,
              chartColors.comparison,
              points.map((p) => p.comparison ?? null),
              { showSymbol: false },
            ),
          ]
        : []),
    ],
  }
}

// --------------------------------------------------------------------------- //
// Stacked columns (one segment per series)
// --------------------------------------------------------------------------- //
export interface StackSeries {
  key: string
  label: string
  color: string
  values: number[]
}

export function stackedColumnsOption(months: string[], series: StackSeries[]): EChartsCoreOption {
  return {
    ...baseOption,
    tooltip: {
      ...(baseOption.tooltip as object),
      formatter: (params: AxisParam[]) => {
        const index = params[0]?.dataIndex ?? 0
        const total = series.reduce((sum, s) => sum + (s.values[index] ?? 0), 0)
        const rows: TooltipRow[] = [...series].reverse().map((s) => ({
          label: s.label,
          value: `${formatCurrency(s.values[index])} · ${formatPercent(total ? (s.values[index] ?? 0) / total : null, 0)}`,
          color: s.color,
          mark: 'bar',
        }))
        return tooltipHtml(formatMonth(months[index] ?? ''), rows, `Total ${formatCurrency(total)}`)
      },
    },
    xAxis: monthAxis(months),
    yAxis: valueAxis(axisFormatter('currency')),
    series: series.map((s, position) => ({
      name: s.label,
      type: 'bar',
      stack: 'total',
      data: s.values,
      barMaxWidth: BAR_MAX_WIDTH,
      itemStyle: {
        color: s.color,
        // A surface-coloured edge is the 2px gap that separates touching segments.
        borderColor: chartColors.surface,
        borderWidth: 1,
        borderRadius: position === series.length - 1 ? [4, 4, 0, 0] : 0,
      },
      emphasis: { focus: 'none' },
    })),
  }
}

// --------------------------------------------------------------------------- //
// Lines (ratios, growth rates)
// --------------------------------------------------------------------------- //
export interface LineSpec {
  label: string
  color: string
  values: (number | null)[]
}

export function linesOption(
  months: string[],
  lines: LineSpec[],
  unit: Unit,
  options: { zeroLine?: boolean; area?: boolean; signed?: boolean } = {},
): EChartsCoreOption {
  const format = (value: number | null | undefined) =>
    unit === 'percent' && options.signed && value != null
      ? `${value > 0 ? '+' : ''}${formatPercent(value)}`
      : formatByUnit(value, unit)
  return {
    ...baseOption,
    tooltip: {
      ...(baseOption.tooltip as object),
      formatter: (params: AxisParam[]) => {
        const index = params[0]?.dataIndex ?? 0
        return tooltipHtml(
          formatMonth(months[index] ?? ''),
          lines.map((line) => ({ label: line.label, value: format(line.values[index]), color: line.color })),
        )
      },
    },
    xAxis: monthAxis(months),
    yAxis: valueAxis(axisFormatter(unit), { scale: !options.zeroLine }),
    series: lines.map((line, index) =>
      lineSeries(line.label, line.color, line.values, {
        connectNulls: false,
        ...(options.area && index === 0 ? { areaStyle: { color: chartColors.seriesSoft } } : {}),
        ...(options.zeroLine && index === 0
          ? {
              markLine: {
                silent: true,
                symbol: 'none',
                label: { show: false },
                lineStyle: { color: chartColors.axis, width: 1, type: 'solid' },
                data: [{ yAxis: 0 }],
              },
            }
          : {}),
      }),
    ),
  }
}

// --------------------------------------------------------------------------- //
// Signed columns (variance per month): colour encodes favourability
// --------------------------------------------------------------------------- //
export interface SignedColumn {
  label: string
  value: number
  favorable: boolean | null
  detail?: TooltipRow[]
}

export function signedColumnsOption(columns: SignedColumn[], unit: Unit = 'currency'): EChartsCoreOption {
  const colorOf = (column: SignedColumn) =>
    column.favorable === null
      ? chartColors.neutral
      : column.favorable
        ? chartColors.favorable
        : chartColors.unfavorable
  return {
    ...baseOption,
    tooltip: {
      ...(baseOption.tooltip as object),
      formatter: (params: AxisParam[]) => {
        const column = columns[params[0]?.dataIndex ?? 0]
        if (!column) return ''
        const verdict =
          column.favorable === null ? 'On target' : column.favorable ? 'Favorable' : 'Unfavorable'
        return tooltipHtml(
          column.label,
          [
            ...(column.detail ?? []),
            {
              label: 'Variance',
              value: unit === 'currency' ? formatSignedCurrency(column.value) : formatPercent(column.value),
              color: colorOf(column),
              mark: 'bar',
            },
          ],
          verdict,
        )
      },
    },
    xAxis: {
      ...categoryAxis(columns.map((c) => c.label)),
      axisLine: { show: false },
    },
    yAxis: valueAxis((value) => (unit === 'currency' ? formatSignedCurrency(value, 0) : formatPercent(value, 0))),
    series: [
      {
        type: 'bar',
        barMaxWidth: BAR_MAX_WIDTH,
        data: columns.map((column) => ({
          value: column.value,
          itemStyle: {
            color: colorOf(column),
            borderRadius: column.value >= 0 ? [4, 4, 0, 0] : [0, 0, 4, 4],
          },
        })),
        markLine: {
          silent: true,
          symbol: 'none',
          label: { show: false },
          lineStyle: { color: chartColors.axis, width: 1, type: 'solid' },
          data: [{ yAxis: 0 }],
        },
      },
    ],
  }
}

// --------------------------------------------------------------------------- //
// Waterfall (bridge between two totals)
// --------------------------------------------------------------------------- //
export interface WaterfallStep {
  label: string
  kind: 'total' | 'effect'
  amount: number
}

export interface WaterfallBar extends WaterfallStep {
  start: number
  end: number
}

/** Positions each step: totals stand on zero, effects float from the running level. */
export function waterfallBars(steps: WaterfallStep[]): WaterfallBar[] {
  let level = 0
  return steps.map((step) => {
    if (step.kind === 'total') {
      level = step.amount
      return { ...step, start: 0, end: step.amount }
    }
    const start = level
    level += step.amount
    return { ...step, start, end: level }
  })
}

export function waterfallOption(
  steps: WaterfallStep[],
  labels: { total: string; effect: string } = {
    total: 'Operating income',
    effect: 'Effect on operating income',
  },
): EChartsCoreOption {
  const bars = waterfallBars(steps)
  const colorOf = (bar: WaterfallBar) =>
    bar.kind === 'total'
      ? chartColors.series
      : bar.amount >= 0
        ? chartColors.favorable
        : chartColors.unfavorable

  // Floating bars are built by stacking: an invisible offset plus a visible part above
  // zero and one below it (ECharts stacks positive and negative values separately), so a
  // bar is drawn correctly whether it sits above, below or across the zero line.
  const layout = bars.map((bar) => {
    const lower = Math.min(bar.start, bar.end)
    const upper = Math.max(bar.start, bar.end)
    if (lower >= 0) return { offset: lower, above: upper - lower, below: null }
    if (upper <= 0) return { offset: upper, above: null, below: lower - upper }
    return { offset: 0, above: upper, below: lower }
  })
  const valueLabel = (bar: WaterfallBar | undefined) =>
    !bar ? '' : bar.kind === 'total' ? formatCurrency(bar.amount) : formatSignedCurrency(bar.amount)
  const visibleSeries = (part: 'above' | 'below') => ({
    type: 'bar' as const,
    stack: 'bridge',
    barMaxWidth: 34,
    data: bars.map((bar, index) => ({
      value: layout[index]?.[part] ?? '-',
      itemStyle: { color: colorOf(bar), borderRadius: 3 },
    })),
    label: {
      show: true,
      position: part === 'above' ? ('top' as const) : ('bottom' as const),
      distance: 6,
      color: chartColors.textSecondary,
      fontSize: 11,
      // Each bar is labelled once: on its upper part when it has one.
      formatter: (param: AxisParam) => {
        const hasUpper = layout[param.dataIndex]?.above != null
        return (part === 'above') === hasUpper ? valueLabel(bars[param.dataIndex]) : ''
      },
    },
  })

  return {
    ...baseOption,
    grid: { left: 4, right: 12, top: 28, bottom: 4, containLabel: true },
    tooltip: {
      ...(baseOption.tooltip as object),
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(148, 163, 184, 0.06)' } },
      formatter: (params: AxisParam[]) => {
        const bar = bars[params[0]?.dataIndex ?? 0]
        if (!bar) return ''
        if (bar.kind === 'total') {
          return tooltipHtml(bar.label, [
            { label: labels.total, value: formatCurrency(bar.amount), color: colorOf(bar), mark: 'bar' },
          ])
        }
        return tooltipHtml(
          bar.label,
          [{ label: labels.effect, value: formatSignedCurrency(bar.amount), color: colorOf(bar), mark: 'bar' }],
          `Running level ${formatCurrency(bar.end)}`,
        )
      },
    },
    xAxis: {
      ...categoryAxis(
        bars.map((bar) => bar.label),
        0,
      ),
      axisLabel: {
        color: chartColors.textMuted,
        fontSize: 11,
        interval: 0,
        width: 76,
        overflow: 'break',
        lineHeight: 14,
        margin: 10,
      },
    },
    yAxis: valueAxis(axisFormatter('currency')),
    series: [
      {
        type: 'bar',
        stack: 'bridge',
        silent: true,
        itemStyle: { color: 'transparent' },
        emphasis: { disabled: true },
        data: layout.map((item) => item.offset),
        barMaxWidth: 34,
      },
      visibleSeries('above'),
      visibleSeries('below'),
    ],
  }
}

// --------------------------------------------------------------------------- //
// Small multiple: one compact line per panel, shared scale across panels
// --------------------------------------------------------------------------- //
export function miniLineOption(
  months: string[],
  values: (number | null)[],
  color: string,
  range: { min: number; max: number },
  name: string,
): EChartsCoreOption {
  return {
    ...baseOption,
    grid: { left: 2, right: 8, top: 8, bottom: 2, containLabel: true },
    tooltip: {
      ...(baseOption.tooltip as object),
      formatter: (params: AxisParam[]) => {
        const index = params[0]?.dataIndex ?? 0
        return tooltipHtml(formatMonth(months[index] ?? ''), [
          { label: name, value: formatPercent(values[index]), color },
        ])
      },
    },
    xAxis: {
      ...categoryAxis(months.map((m) => formatMonth(m, 'short'))),
      axisLabel: { color: chartColors.textMuted, fontSize: 10, interval: Math.max(0, Math.ceil(months.length / 4) - 1) },
    },
    yAxis: valueAxis((value) => formatPercent(value, 0), { min: range.min, max: range.max, interval: 0.1 }),
    series: [
      lineSeries(name, color, values, {
        showSymbol: false,
        areaStyle: { color, opacity: 0.1 },
      }),
    ],
  }
}
