import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export interface RankedBarRow {
  key: string
  label: string
  value: number
  /** Value printed at the end of the row. */
  valueText: string
  /** Secondary figure (share, margin, change…) shown beside the value. */
  detail?: ReactNode
  /** Reference value drawn as a tick on the bar's scale (for example the budget). */
  marker?: number | null
  /** Identity swatch; when set it also colours the bar. */
  color?: string
}

interface RankedBarsProps {
  rows: RankedBarRow[]
  /** Accessible name of the list. */
  label: string
  /** Bar colour for a single series (one hue: the bars are not separate series). */
  color?: string
  markerLabel?: string
  /** Spread the rows over the full height of the container instead of stacking them. */
  fill?: boolean
  className?: string
}

/**
 * Ranked horizontal bars on one baseline. Every value is printed, so nothing depends on
 * hovering and the list is readable by assistive technology as-is.
 */
export function RankedBars({ rows, label, color = 'var(--series)', markerLabel, fill, className }: RankedBarsProps) {
  const scaleMax = Math.max(1, ...rows.map((row) => Math.max(row.value, row.marker ?? 0)))
  return (
    <ul aria-label={label} className={cn(fill ? 'flex h-full flex-col justify-between gap-3' : 'space-y-3', className)}>
      {rows.map((row) => {
        const width = Math.max(0, (row.value / scaleMax) * 100)
        const marker = row.marker != null ? (row.marker / scaleMax) * 100 : null
        return (
          <li key={row.key} className="group">
            <div className="flex items-baseline justify-between gap-3 text-[13px]">
              <span className="flex min-w-0 items-center gap-2 text-foreground">
                {row.color ? (
                  <span aria-hidden className="size-2 shrink-0 rounded-[2px]" style={{ backgroundColor: row.color }} />
                ) : null}
                <span className="truncate">{row.label}</span>
              </span>
              <span className="tabular flex shrink-0 items-baseline gap-2.5">
                {row.detail ? <span className="text-xs text-muted-foreground">{row.detail}</span> : null}
                <span className="font-medium text-foreground">{row.valueText}</span>
              </span>
            </div>
            <div className="relative mt-1.5 h-2 rounded-r-[4px] bg-track">
              <div
                className="h-full rounded-r-[4px] transition-[width] duration-300 group-hover:brightness-125"
                style={{ width: `${width}%`, backgroundColor: row.color ?? color }}
              />
              {marker != null ? (
                <span
                  aria-hidden
                  title={markerLabel}
                  className="absolute -top-1 h-4 w-0.5 rounded-full bg-foreground/80"
                  style={{ left: `calc(${Math.min(100, marker)}% - 1px)` }}
                />
              ) : null}
            </div>
          </li>
        )
      })}
    </ul>
  )
}
