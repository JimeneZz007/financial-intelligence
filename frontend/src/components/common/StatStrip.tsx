import type { ReactNode } from 'react'

import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

export interface Stat {
  label: string
  value: string
  /** Change or status shown under the value. */
  detail?: ReactNode
}

interface StatStripProps {
  stats: Stat[] | undefined
  /** Number of placeholders while loading. */
  count?: number
  stale?: boolean
  label: string
}

/** A row of secondary figures that frame a view: quieter than the headline KPI tiles. */
export function StatStrip({ stats, count = 4, stale, label }: StatStripProps) {
  return (
    <dl
      aria-label={label}
      className={cn(
        'grid grid-cols-2 overflow-hidden rounded-xl border bg-card transition-opacity duration-200 lg:grid-cols-4',
        stale && 'opacity-55',
      )}
    >
      {stats
        ? stats.map((stat, index) => (
            <div
              key={stat.label}
              className={cn(
                'min-w-0 px-5 py-4',
                // Hairlines between cells, without an outer border of their own.
                index % 2 === 1 && 'border-l',
                index >= 2 && 'border-t lg:border-t-0',
                index >= 1 && 'lg:border-l',
              )}
            >
              <dt className="truncate text-xs font-medium text-muted-foreground">{stat.label}</dt>
              <dd className="mt-1.5 text-xl leading-none font-semibold tracking-tight text-foreground">{stat.value}</dd>
              {stat.detail ? <dd className="mt-2 text-xs text-muted-foreground">{stat.detail}</dd> : null}
            </div>
          ))
        : Array.from({ length: count }, (_, index) => (
            <div key={index} className="px-5 py-4" role="status" aria-label="Loading">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="mt-3 h-6 w-20" />
              <Skeleton className="mt-3 h-3 w-28" />
            </div>
          ))}
    </dl>
  )
}
