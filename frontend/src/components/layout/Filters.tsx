import { ArrowLeftRight, Building2, CalendarRange, Check, ChevronDown } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { ComparisonMode } from '@/lib/api'
import { useFilters } from '@/lib/filters'
import { formatMonth } from '@/lib/format'
import { cn } from '@/lib/utils'

const TRIGGER_CLASS = 'h-9 justify-between gap-2 px-3 text-[13px] font-medium'

/** Period: presets first (the common case), custom month range behind a divider. */
export function PeriodFilter() {
  const { start, end, presets, activePreset, dimensions, setPeriod } = useFilters()
  const [open, setOpen] = useState(false)
  const [customStart, setCustomStart] = useState(start)
  const [customEnd, setCustomEnd] = useState(end)
  const months = dimensions.period.months
  const label = activePreset?.label ?? `${formatMonth(start)} – ${formatMonth(end)}`
  const invalidRange = customStart > customEnd

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next)
        if (next) {
          setCustomStart(start)
          setCustomEnd(end)
        }
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="outline" className={TRIGGER_CLASS} aria-label={`Period: ${label}`} data-testid="period-filter">
          <CalendarRange className="text-muted-foreground" />
          <span>{label}</span>
          <ChevronDown className="text-muted-foreground" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 p-0">
        <ul className="p-1.5" aria-label="Period presets">
          {presets.map((preset) => {
            const selected = activePreset?.id === preset.id
            return (
              <li key={preset.id}>
                <button
                  type="button"
                  aria-pressed={selected}
                  onClick={() => {
                    setPeriod(preset.start, preset.end)
                    setOpen(false)
                  }}
                  className={cn(
                    'flex h-9 w-full items-center justify-between rounded-md px-2.5 text-left text-[13px] hover:bg-accent/70',
                    selected ? 'font-semibold text-foreground' : 'text-foreground/90',
                  )}
                >
                  <span>{preset.label}</span>
                  <span className="flex items-center gap-2 text-xs font-normal text-muted-foreground">
                    {formatMonth(preset.start, 'axis')} – {formatMonth(preset.end, 'axis')}
                    <Check aria-hidden className={cn('size-4 text-brand', !selected && 'invisible')} strokeWidth={3} />
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
        <div className="border-t p-3">
          <p className="text-xs font-medium text-muted-foreground">Custom range</p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <MonthSelect label="From" value={customStart} months={months} onChange={setCustomStart} />
            <MonthSelect label="To" value={customEnd} months={months} onChange={setCustomEnd} />
          </div>
          {invalidRange ? (
            <p role="alert" className="mt-2 text-xs text-unfavorable-text">
              The start month must not be after the end month.
            </p>
          ) : null}
          <Button
            size="sm"
            className="mt-3 w-full"
            disabled={invalidRange}
            onClick={() => {
              setPeriod(customStart, customEnd)
              setOpen(false)
            }}
          >
            Apply range
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}

function MonthSelect({
  label,
  value,
  months,
  onChange,
}: {
  label: string
  value: string
  months: string[]
  onChange: (value: string) => void
}) {
  return (
    <label className="block text-[11px] text-muted-foreground">
      {label}
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="mt-1 h-8 w-full text-xs" aria-label={`${label} month`}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent className="max-h-64">
          {months.map((month) => (
            <SelectItem key={month} value={month} className="text-xs">
              {formatMonth(month)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </label>
  )
}

/** Business units: multi-select; none selected means all of them. */
export function UnitFilter() {
  const { units, dimensions, setUnits, toggleUnit } = useFilters()
  const all = dimensions.business_units
  const label =
    units.length === 0
      ? 'All business units'
      : units.length === 1
        ? (all.find((unit) => unit.code === units[0])?.name ?? units[0])
        : `${units.length} business units`

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className={TRIGGER_CLASS} aria-label={`Business unit: ${label}`} data-testid="unit-filter">
          <Building2 className="text-muted-foreground" />
          <span className="max-w-40 truncate">{label}</span>
          <ChevronDown className="text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        <DropdownMenuLabel className="text-xs text-muted-foreground">Business units</DropdownMenuLabel>
        <DropdownMenuItem
          onSelect={() => setUnits([])}
          className="justify-between text-[13px]"
          data-testid="unit-option-all"
        >
          All business units
          <Check aria-hidden className={cn('size-4 text-brand', units.length > 0 && 'invisible')} strokeWidth={3} />
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {all.map((unit) => (
          <DropdownMenuCheckboxItem
            key={unit.code}
            checked={units.includes(unit.code)}
            onCheckedChange={(checked) => toggleUnit(unit.code, checked === true)}
            // Keep the menu open: several units are usually picked in one go.
            onSelect={(event) => event.preventDefault()}
            className="text-[13px]"
            data-testid={`unit-option-${unit.code}`}
          >
            <span className="flex flex-col">
              {unit.name}
              <span className="text-[11px] text-muted-foreground">{unit.sales_channel}</span>
            </span>
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

const COMPARE_OPTIONS: { value: ComparisonMode; label: string; hint: string }[] = [
  { value: 'previous_year', label: 'vs prior year', hint: 'Same months one year earlier' },
  { value: 'previous_period', label: 'vs prior period', hint: 'Equally long period just before' },
]

export function CompareFilter() {
  const { compare, setCompare } = useFilters()
  return (
    <Select value={compare} onValueChange={(value) => setCompare(value as ComparisonMode)}>
      <SelectTrigger className={cn(TRIGGER_CLASS, 'w-auto')} aria-label="Comparison basis" data-testid="compare-filter">
        <ArrowLeftRight className="text-muted-foreground" />
        <SelectValue />
      </SelectTrigger>
      <SelectContent align="start">
        {COMPARE_OPTIONS.map((option) => (
          <SelectItem key={option.value} value={option.value} className="text-[13px]">
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

/** The single filter row that scopes every chart, table and finding below it. */
export function FilterBar() {
  return (
    <div role="group" aria-label="Global filters" className="flex flex-wrap items-center gap-2">
      <PeriodFilter />
      <UnitFilter />
      <CompareFilter />
    </div>
  )
}
