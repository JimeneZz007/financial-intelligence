import { Download } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { apiUrl } from '@/lib/api'
import { useFilters } from '@/lib/filters'

interface SegmentedProps<T extends string> {
  /** Accessible name of the group. */
  label: string
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
}

/** Single-choice switch for a panel (metric, grouping, basis). */
export function Segmented<T extends string>({ label, value, options, onChange }: SegmentedProps<T>) {
  return (
    <ToggleGroup
      type="single"
      size="sm"
      variant="outline"
      spacing={0}
      value={value}
      aria-label={label}
      // On narrow screens the options scroll sideways instead of widening the page.
      className="scrollbar-thin max-w-full overflow-x-auto"
      // Radix emits "" when the active item is pressed again: a choice must stay selected.
      onValueChange={(next) => next && onChange(next as T)}
    >
      {options.map((option) => (
        <ToggleGroupItem
          key={option.value}
          value={option.value}
          className="px-2.5 text-xs text-muted-foreground data-[state=on]:bg-accent data-[state=on]:text-foreground"
        >
          {option.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  )
}

/** Expands or collapses a long table instead of nesting a scroll area inside the card. */
export function ShowAllToggle({
  expanded,
  total,
  noun,
  onToggle,
}: {
  expanded: boolean
  total: number
  noun: string
  onToggle: () => void
}) {
  return (
    <Button variant="ghost" size="sm" aria-expanded={expanded} onClick={onToggle} className="mt-2 text-xs text-brand hover:text-brand">
      {expanded ? 'Show fewer' : `Show all ${total} ${noun}`}
    </Button>
  )
}

type ExportDataset =
  | 'monthly-pnl'
  | 'budget-by-account'
  | 'sales-by-product'
  | 'expenses-by-cost-center'
  | 'anomalies'

/** Downloads the detail behind a view as CSV, with the filters currently applied. */
export function ExportButton({ dataset, label = 'Export CSV' }: { dataset: ExportDataset; label?: string }) {
  const { apiParams } = useFilters()
  return (
    <Button asChild variant="outline" size="sm">
      <a href={apiUrl(`/exports/${dataset}`, apiParams)} download data-testid={`export-${dataset}`}>
        <Download /> {label}
      </a>
    </Button>
  )
}
