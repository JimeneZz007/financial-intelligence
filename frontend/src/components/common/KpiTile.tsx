import type { LucideIcon } from 'lucide-react'

import { Delta, directionOf } from '@/components/common/Delta'
import { Skeleton } from '@/components/ui/skeleton'
import type { Kpi } from '@/lib/api'
import { formatByUnit, formatChange } from '@/lib/format'
import { cn } from '@/lib/utils'

interface SparklineProps {
  values: (number | null | undefined)[]
  className?: string
}

/** Trend of the period: de-emphasised line, the latest point in the accent. */
export function Sparkline({ values, className }: SparklineProps) {
  const points = values.filter((v): v is number => v != null)
  if (points.length < 2) return <div className={className} aria-hidden />
  const width = 120
  const height = 36
  const pad = 4
  const min = Math.min(...points)
  const max = Math.max(...points)
  const span = max - min || 1
  const coords = points.map((value, index) => {
    const x = pad + (index / (points.length - 1)) * (width - 2 * pad)
    const y = height - pad - ((value - min) / span) * (height - 2 * pad)
    return [x, y] as const
  })
  const path = coords.map(([x, y], index) => `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const last = coords[coords.length - 1]!
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className={className} aria-hidden preserveAspectRatio="none">
      <path d={path} fill="none" stroke="#4b5a75" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      <circle cx={last[0]} cy={last[1]} r="3" fill="#38bdf8" stroke="#111a2c" strokeWidth="1.5" />
    </svg>
  )
}

interface KpiTileProps {
  kpi: Kpi
  icon: LucideIcon
  comparisonLabel: string
  stale?: boolean
}

/** Stat tile: label, value, change vs the comparison period, variance vs budget, trend. */
export function KpiTile({ kpi, icon: Icon, comparisonLabel, stale }: KpiTileProps) {
  const hasComparison = kpi.comparison_value != null
  const hasBudget = kpi.budget_value != null
  return (
    <article
      aria-label={kpi.label}
      className={cn(
        'relative flex min-w-0 flex-col rounded-xl border bg-card p-5 transition-opacity duration-200',
        stale && 'opacity-55',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-[13px] font-medium text-muted-foreground">{kpi.label}</h3>
        <span className="flex size-7 items-center justify-center rounded-lg bg-muted text-muted-foreground">
          <Icon aria-hidden className="size-3.5" />
        </span>
      </div>

      <div className="mt-3 flex items-end justify-between gap-3">
        <p className="text-[28px] leading-none font-semibold tracking-tight text-foreground" data-testid={`kpi-value-${kpi.id}`}>
          {formatByUnit(kpi.value, kpi.unit)}
        </p>
        <Sparkline values={kpi.sparkline} className="h-9 w-24 shrink-0" />
      </div>

      <dl className="mt-4 space-y-1.5 border-t pt-3 text-xs">
        <div className="flex items-center justify-between gap-2">
          <dt className="text-muted-foreground">vs {comparisonLabel}</dt>
          <dd>
            {hasComparison ? (
              <Delta
                text={formatChange(kpi.change, kpi.change_pct, kpi.unit)}
                direction={directionOf(kpi.change)}
                status={kpi.comparison_status}
              />
            ) : (
              <span className="text-subtle" title="The comparison period has no data">
                No data
              </span>
            )}
          </dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-muted-foreground">vs budget</dt>
          <dd>
            {hasBudget ? (
              <Delta
                text={formatChange(kpi.budget_variance, kpi.budget_variance_pct, kpi.unit)}
                direction={directionOf(kpi.budget_variance)}
                status={kpi.budget_status}
              />
            ) : (
              <span className="text-subtle">No data</span>
            )}
          </dd>
        </div>
      </dl>
    </article>
  )
}

export function KpiTileSkeleton() {
  return (
    <div className="rounded-xl border bg-card p-5" role="status" aria-label="Loading indicator">
      <Skeleton className="h-4 w-28" />
      <Skeleton className="mt-4 h-8 w-32" />
      <Skeleton className="mt-5 h-3 w-full" />
      <Skeleton className="mt-2 h-3 w-full" />
    </div>
  )
}
