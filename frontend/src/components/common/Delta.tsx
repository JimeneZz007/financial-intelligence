import { ArrowDownRight, ArrowUpRight, Check, Minus, TriangleAlert } from 'lucide-react'

import type { Favorability } from '@/lib/api'
import { cn } from '@/lib/utils'

const TONE_CLASS: Record<Favorability | 'none', string> = {
  favorable: 'text-favorable-text',
  unfavorable: 'text-unfavorable-text',
  on_target: 'text-muted-foreground',
  none: 'text-muted-foreground',
}

interface DeltaProps {
  /** Formatted change, e.g. "+13.4%" or "-1.3 pp". */
  text: string
  /** Direction of the number itself; decides the arrow. */
  direction: 'up' | 'down' | 'flat'
  /** Whether the change is good or bad for profit; decides the colour. */
  status?: Favorability | null
  className?: string
}

/**
 * A signed change. Direction and meaning are independent: costs going up show an "up"
 * arrow in the unfavourable colour. Meaning is never carried by colour alone: the arrow,
 * the sign and a screen-reader label repeat it.
 */
export function Delta({ text, direction, status, className }: DeltaProps) {
  const Icon = direction === 'up' ? ArrowUpRight : direction === 'down' ? ArrowDownRight : Minus
  const tone = status ?? 'none'
  return (
    <span className={cn('tabular inline-flex items-center gap-0.5 font-medium', TONE_CLASS[tone], className)}>
      <Icon aria-hidden className="size-3.5 shrink-0" />
      {text}
      {status ? <span className="sr-only"> ({STATUS_LABEL[status]})</span> : null}
    </span>
  )
}

export const directionOf = (value: number | null | undefined): 'up' | 'down' | 'flat' =>
  value == null || value === 0 ? 'flat' : value > 0 ? 'up' : 'down'

export const STATUS_LABEL: Record<Favorability, string> = {
  favorable: 'Favorable',
  unfavorable: 'Unfavorable',
  on_target: 'On target',
}

const STATUS_BADGE_CLASS: Record<Favorability, string> = {
  favorable: 'bg-favorable/12 text-favorable-text ring-favorable/25',
  unfavorable: 'bg-unfavorable/12 text-unfavorable-text ring-unfavorable/25',
  on_target: 'bg-muted text-muted-foreground ring-border',
}

/** Favourability as a labelled pill: icon + word, so colour is only a reinforcement. */
export function StatusBadge({ status, className }: { status: Favorability; className?: string }) {
  const Icon = status === 'favorable' ? Check : status === 'unfavorable' ? TriangleAlert : Minus
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset',
        STATUS_BADGE_CLASS[status],
        className,
      )}
    >
      <Icon aria-hidden className="size-3" />
      {STATUS_LABEL[status]}
    </span>
  )
}
