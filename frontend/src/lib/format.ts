/** Number, currency and date formatting shared by every view. */

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export const EMPTY = '—'

const isMissing = (value: number | null | undefined): value is null | undefined =>
  value === null || value === undefined || !Number.isFinite(value)

/**
 * 1284 -> "1,284" · 12940 -> "12.9K" · 345200 -> "345K" · 4000000 -> "4.0M"
 *
 * Millions always keep their decimals ("4.0M", never "4M") so figures in a column or a
 * row of tiles carry the same precision. Thousands drop them from 100K up, where three
 * significant digits are already shown.
 */
export function formatCompact(value: number | null | undefined, digits = 1): string {
  if (isMissing(value)) return EMPTY
  const magnitude = Math.abs(value)
  const sign = value < 0 ? '-' : ''
  if (magnitude >= 999.95e6) return `${sign}${(magnitude / 1e9).toFixed(Math.max(digits, 1))}B`
  if (magnitude >= 999.5e3) return `${sign}${(magnitude / 1e6).toFixed(digits)}M`
  if (magnitude >= 99.95e3) return `${sign}${(magnitude / 1e3).toFixed(0)}K`
  if (magnitude >= 1e4) return `${sign}${(magnitude / 1e3).toFixed(digits)}K`
  return `${sign}${Math.round(magnitude).toLocaleString('en-US')}`
}

/** Compact currency for headlines and axes: "$59.1M", "-$345K". */
export function formatCurrency(value: number | null | undefined, digits = 1): string {
  if (isMissing(value)) return EMPTY
  const text = formatCompact(Math.abs(value), digits)
  return `${value < 0 ? '-' : ''}$${text}`
}

/** Full currency for tables: "$59,053,742". */
export function formatCurrencyFull(value: number | null | undefined): string {
  if (isMissing(value)) return EMPTY
  const text = Math.round(Math.abs(value)).toLocaleString('en-US')
  return `${value < 0 ? '-' : ''}$${text}`
}

/** Signed compact currency for variances: "+$356K", "-$1.1M". */
export function formatSignedCurrency(value: number | null | undefined, digits = 1): string {
  if (isMissing(value)) return EMPTY
  if (value === 0) return '$0'
  return `${value > 0 ? '+' : '-'}$${formatCompact(Math.abs(value), digits)}`
}

/** Signed full currency for table columns, so every row has the same precision: "+$55,371". */
export function formatSignedCurrencyFull(value: number | null | undefined): string {
  if (isMissing(value)) return EMPTY
  const rounded = Math.round(value)
  if (rounded === 0) return '$0'
  return `${rounded > 0 ? '+' : '-'}$${Math.abs(rounded).toLocaleString('en-US')}`
}

/** Ratio (0.309) -> "30.9%". */
export function formatPercent(ratio: number | null | undefined, digits = 1): string {
  if (isMissing(ratio)) return EMPTY
  return `${(ratio * 100).toFixed(digits)}%`
}

/** Ratio (0.134) -> "+13.4%". */
export function formatSignedPercent(ratio: number | null | undefined, digits = 1): string {
  if (isMissing(ratio)) return EMPTY
  const text = (Math.abs(ratio) * 100).toFixed(digits)
  if (Number(text) === 0) return `${text}%`
  return `${ratio > 0 ? '+' : '-'}${text}%`
}

/** Difference of two ratios (-0.013) -> "-1.3 pp". */
export function formatPoints(difference: number | null | undefined, digits = 1): string {
  if (isMissing(difference)) return EMPTY
  const text = (Math.abs(difference) * 100).toFixed(digits)
  if (Number(text) === 0) return `${text} pp`
  return `${difference > 0 ? '+' : '-'}${text} pp`
}

export function formatInteger(value: number | null | undefined): string {
  if (isMissing(value)) return EMPTY
  return Math.round(value).toLocaleString('en-US')
}

/** "2025-03" -> "Mar 2025" (long) or "Mar" / "Mar 25" (axis). */
export function formatMonth(month: string, style: 'long' | 'short' | 'axis' = 'long'): string {
  const [year, monthNumber] = month.split('-')
  const name = MONTH_NAMES[Number(monthNumber) - 1]
  if (!year || !name) return month
  if (style === 'short') return name
  if (style === 'axis') return `${name} ${year.slice(2)}`
  return `${name} ${year}`
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return EMPTY
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return EMPTY
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export type Unit = 'currency' | 'percent' | 'number'

export function formatByUnit(value: number | null | undefined, unit: Unit): string {
  if (unit === 'percent') return formatPercent(value)
  if (unit === 'currency') return formatCurrency(value)
  return formatInteger(value)
}

/** A change: relative for amounts, percentage points for ratios. */
export function formatChange(
  change: number | null | undefined,
  changePct: number | null | undefined,
  unit: Unit,
): string {
  if (unit === 'percent') return formatPoints(change)
  return formatSignedPercent(changePct)
}
