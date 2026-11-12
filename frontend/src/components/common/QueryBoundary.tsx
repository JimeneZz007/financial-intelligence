import type { UseQueryResult } from '@tanstack/react-query'
import { CircleAlert, Inbox, RotateCw } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

interface QueryBoundaryProps<T> {
  query: UseQueryResult<T>
  /** Height reserved while loading and for error / empty states, to avoid layout jumps. */
  minHeight?: number
  isEmpty?: (data: T) => boolean
  emptyTitle?: string
  emptyHint?: string
  skeleton?: ReactNode
  children: (data: T) => ReactNode
}

/** Renders the loading, error, empty or ready state of a query. */
export function QueryBoundary<T>({
  query,
  minHeight = 200,
  isEmpty,
  emptyTitle = 'No data for this selection',
  emptyHint = 'Try a wider period or a different business unit.',
  skeleton,
  children,
}: QueryBoundaryProps<T>) {
  if (query.data !== undefined) {
    if (isEmpty?.(query.data)) {
      return <StateMessage icon={<Inbox />} title={emptyTitle} hint={emptyHint} minHeight={minHeight} />
    }
    return <>{children(query.data)}</>
  }
  if (query.isError) {
    return (
      <StateMessage
        tone="error"
        icon={<CircleAlert />}
        title="This data could not be loaded"
        hint={query.error instanceof Error ? query.error.message : 'Unexpected error.'}
        minHeight={minHeight}
        action={
          <Button variant="outline" size="sm" onClick={() => void query.refetch()}>
            <RotateCw /> Try again
          </Button>
        }
      />
    )
  }
  return (
    <div role="status" aria-label="Loading" style={{ minHeight }}>
      {skeleton ?? <Skeleton className="h-full w-full rounded-lg" style={{ minHeight }} />}
    </div>
  )
}

interface StateMessageProps {
  icon: ReactNode
  title: string
  hint?: string
  action?: ReactNode
  minHeight?: number
  tone?: 'neutral' | 'error'
}

export function StateMessage({ icon, title, hint, action, minHeight = 200, tone = 'neutral' }: StateMessageProps) {
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-6 py-8 text-center"
      style={{ minHeight }}
    >
      <span
        className={cn(
          'flex size-9 items-center justify-center rounded-full bg-muted [&_svg]:size-4',
          tone === 'error' ? 'text-unfavorable-text' : 'text-muted-foreground',
        )}
      >
        {icon}
      </span>
      <p className="text-sm font-medium text-foreground">{title}</p>
      {hint ? <p className="max-w-sm text-xs text-muted-foreground">{hint}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  )
}

/** True while a filter change is loading and the previous data is still displayed. */
export function isStale(query: UseQueryResult<unknown>): boolean {
  return query.isPlaceholderData
}
