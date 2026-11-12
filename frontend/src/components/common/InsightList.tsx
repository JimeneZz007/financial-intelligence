import { ChevronDown, CircleDot, TrendingDown, TrendingUp } from 'lucide-react'

import type { Insight } from '@/lib/api'
import { formatCurrencyFull, formatInteger, formatPercent } from '@/lib/format'
import { cn } from '@/lib/utils'

const CATEGORY_LABEL: Record<Insight['category'], string> = {
  performance: 'Performance',
  budget: 'Budget',
  expenses: 'Expenses',
  profitability: 'Profitability',
  trend: 'Trend',
  anomaly: 'Anomaly',
}

const TONE = {
  positive: { icon: TrendingUp, className: 'bg-favorable/12 text-favorable-text', label: 'Positive' },
  negative: { icon: TrendingDown, className: 'bg-unfavorable/12 text-unfavorable-text', label: 'Negative' },
  neutral: { icon: CircleDot, className: 'bg-muted text-muted-foreground', label: 'Neutral' },
} as const

function evidenceValue(value: number | null | undefined, unit: string): string {
  if (unit === 'percent') return formatPercent(value, 2)
  if (unit === 'currency') return formatCurrencyFull(value)
  return formatInteger(value)
}

interface InsightListProps {
  insights: Insight[]
  /** Show at most this many findings. */
  limit?: number
  /** Lay the findings out as a grid of cards instead of a single column. */
  grid?: boolean
}

/**
 * Findings computed by the API for the current filters. Each one can be expanded to show
 * the exact figures it was built from.
 */
export function InsightList({ insights, limit, grid }: InsightListProps) {
  const visible = limit ? insights.slice(0, limit) : insights
  return (
    <ul
      className={cn(grid ? 'grid gap-3 md:grid-cols-2 xl:grid-cols-3' : 'divide-y')}
      aria-label="Findings"
    >
      {visible.map((insight) => {
        const tone = TONE[insight.tone]
        const Icon = tone.icon
        return (
          <li
            key={insight.id}
            className={cn(grid ? 'rounded-lg border bg-surface-raised/40 p-4' : 'py-3.5 first:pt-0 last:pb-0')}
            data-testid={`insight-${insight.id}`}
          >
            <div className="flex gap-3">
              <span className={cn('mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg', tone.className)}>
                <Icon aria-hidden className="size-3.5" />
                <span className="sr-only">{tone.label} finding</span>
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-medium tracking-wide text-subtle uppercase">
                  {CATEGORY_LABEL[insight.category]}
                </p>
                <h3 className="mt-0.5 text-[13px] leading-snug font-semibold text-foreground">{insight.title}</h3>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{insight.detail}</p>
                <details className="group mt-1.5">
                  <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded text-[11px] font-medium text-brand/90 hover:text-brand [&::-webkit-details-marker]:hidden">
                    <ChevronDown aria-hidden className="size-3 transition-transform group-open:rotate-180" />
                    Evidence
                  </summary>
                  <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 rounded-lg bg-muted/60 px-3 py-2 text-[11px]">
                    {insight.evidence.map((item) => (
                      <div key={item.label} className="contents">
                        <dt className="text-muted-foreground">{item.label}</dt>
                        <dd className="tabular text-right font-medium text-foreground">
                          {evidenceValue(item.value, item.unit)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </details>
              </div>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
