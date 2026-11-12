/**
 * Chart colours and shared ECharts fragments.
 *
 * Every colour has one job (see docs/UI_DESIGN.md):
 *   - `series`     the single-series data hue
 *   - `reference`  budget / comparison lines: neutral, so they read as context
 *   - `favorable` / `unfavorable`  polarity; the pair is validated for colour-vision
 *     deficiency (worst simulated distance 11.2, target >= 8)
 *   - `units`      identity of the four business units, in fixed order; validated for
 *     forms where only neighbours touch (stacked or grouped bars)
 * Greens and reds are never used for identity, so they always mean good / bad.
 */
import type { EChartsCoreOption } from 'echarts/core'

export const chartColors = {
  surface: '#111a2c',
  raised: '#16213a',
  series: '#3987e5',
  seriesSoft: 'rgba(57, 135, 229, 0.12)',
  budget: '#c7d0e0',
  comparison: '#66748c',
  favorable: '#12a594',
  unfavorable: '#e5604d',
  neutral: '#4b5a75',
  text: '#e6ebf4',
  textSecondary: '#93a0b8',
  textMuted: '#8391a9',
  grid: '#1b2740',
  axis: '#2a3854',
} as const

/** Business-unit hues in fixed order: colour follows the unit, never its rank. */
export const UNIT_COLORS: Record<string, string> = {
  RET: '#3987e5',
  ECM: '#c98500',
  WHS: '#d55181',
  COR: '#9085e9',
}
const UNIT_FALLBACK = '#4b5a75'

export const unitColor = (code: string): string => UNIT_COLORS[code] ?? UNIT_FALLBACK

/** One-hue ramp for magnitude on the dark surface: near zero recedes, more is brighter. */
export const SEQUENTIAL_RAMP = ['#15233d', '#18305a', '#1c3e75', '#204c8f', '#255ba8', '#2d6fc8', '#3987e5']

function rampIndex(share: number): number {
  const clamped = Math.min(1, Math.max(0, share))
  return Math.min(SEQUENTIAL_RAMP.length - 1, Math.floor(clamped * SEQUENTIAL_RAMP.length))
}

export function sequentialColor(share: number): string {
  return SEQUENTIAL_RAMP[rampIndex(share)] ?? SEQUENTIAL_RAMP[0]!
}

/** Ink for a label printed on a ramp step: white, except near-black on the brightest step. */
export function sequentialInk(share: number): string {
  return rampIndex(share) === SEQUENTIAL_RAMP.length - 1 ? '#04121c' : '#ffffff'
}

/** Diverging scale for polarity: two opposite hues around a neutral midpoint. */
export function divergingColor(impactShare: number): string {
  const magnitude = Math.min(1, Math.abs(impactShare))
  // Small variances stay neutral so only the ones that matter draw the eye.
  if (magnitude < 0.06) return '#1c2842'
  // Capped so white labels keep at least 4.5:1 on the strongest cells.
  const alpha = 0.12 + 0.58 * magnitude
  return impactShare > 0 ? `rgba(18, 165, 148, ${alpha})` : `rgba(229, 96, 77, ${alpha})`
}

const FONT_FAMILY = '"Geist Variable", system-ui, -apple-system, "Segoe UI", sans-serif'

export const baseTextStyle = { fontFamily: FONT_FAMILY, color: chartColors.textSecondary, fontSize: 12 }

export const baseOption: EChartsCoreOption = {
  animationDuration: 350,
  animationDurationUpdate: 250,
  textStyle: baseTextStyle,
  grid: { left: 4, right: 12, top: 16, bottom: 4, containLabel: true },
  tooltip: {
    trigger: 'axis',
    confine: true,
    backgroundColor: '#152038',
    borderColor: 'rgba(148, 163, 184, 0.22)',
    borderWidth: 1,
    padding: [10, 12],
    textStyle: { fontFamily: FONT_FAMILY, color: chartColors.text, fontSize: 12 },
    extraCssText: 'box-shadow: 0 12px 32px rgba(2, 6, 16, 0.55); border-radius: 10px;',
    axisPointer: {
      type: 'line',
      lineStyle: { color: 'rgba(148, 163, 184, 0.35)', width: 1, type: 'solid' },
    },
  },
}

export const categoryAxis = (labels: string[], interval: number | 'auto' = 'auto') => ({
  type: 'category' as const,
  data: labels,
  axisLine: { lineStyle: { color: chartColors.axis } },
  axisTick: { show: false },
  axisLabel: { color: chartColors.textMuted, fontSize: 11, margin: 10, interval, hideOverlap: true },
})

export const valueAxis = (formatter: (value: number) => string, extra: Record<string, unknown> = {}) => ({
  type: 'value' as const,
  axisLine: { show: false },
  axisTick: { show: false },
  splitNumber: 4,
  splitLine: { lineStyle: { color: chartColors.grid, width: 1, type: 'solid' as const } },
  axisLabel: { color: chartColors.textMuted, fontSize: 11, formatter },
  ...extra,
})

/** Escapes text placed in HTML tooltips: labels come from data and are untrusted. */
export function escapeHtml(text: string): string {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

export interface TooltipRow {
  label: string
  value: string
  color?: string
  /** 'line' keys a line series, 'bar' a filled mark. */
  mark?: 'line' | 'bar'
  muted?: boolean
}

/** Tooltip body: the value leads, the series name follows. */
export function tooltipHtml(title: string, rows: TooltipRow[], footer?: string): string {
  const body = rows
    .map((row) => {
      const key = row.color
        ? `<span style="display:inline-block;width:${row.mark === 'bar' ? 8 : 12}px;height:${
            row.mark === 'bar' ? 8 : 2
          }px;border-radius:2px;background:${row.color};margin-right:8px;vertical-align:middle"></span>`
        : ''
      return `<div style="display:flex;justify-content:space-between;gap:20px;align-items:center;margin-top:5px">
        <span style="color:${chartColors.textSecondary}">${key}${escapeHtml(row.label)}</span>
        <span style="font-weight:600;font-variant-numeric:tabular-nums;color:${
          row.muted ? chartColors.textSecondary : chartColors.text
        }">${escapeHtml(row.value)}</span>
      </div>`
    })
    .join('')
  const foot = footer
    ? `<div style="margin-top:8px;padding-top:7px;border-top:1px solid rgba(148,163,184,0.16);color:${chartColors.textSecondary}">${escapeHtml(footer)}</div>`
    : ''
  return `<div style="min-width:180px"><div style="font-weight:600;color:${chartColors.text}">${escapeHtml(
    title,
  )}</div>${body}${foot}</div>`
}
