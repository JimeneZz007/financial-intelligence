/**
 * Global filters (period, business units, comparison basis).
 *
 * The URL is the single source of truth: filters survive navigation and reloads, and a
 * link reproduces exactly the view someone is looking at.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, type ReactNode } from 'react'
import { useSearchParams } from 'react-router'

import type { ComparisonMode, DimensionsResponse, QueryParams } from './api'

export interface PeriodPreset {
  id: string
  label: string
  start: string
  end: string
}

export interface FilterState {
  start: string
  end: string
  units: string[]
  compare: ComparisonMode
}

interface FiltersContextValue extends FilterState {
  dimensions: DimensionsResponse
  presets: PeriodPreset[]
  activePreset: PeriodPreset | null
  /** Parameters every analytic endpoint accepts. */
  apiParams: QueryParams
  /** Query string to carry the filters across routes ("" or "?from=…"). */
  search: string
  setPeriod: (start: string, end: string) => void
  /** Adds or removes one unit; safe to call several times before the URL has updated. */
  toggleUnit: (code: string, selected: boolean) => void
  setUnits: (units: string[]) => void
  setCompare: (compare: ComparisonMode) => void
  reset: () => void
}

const FiltersContext = createContext<FiltersContextValue | null>(null)

const COMPARE_CODES: Record<string, ComparisonMode> = { py: 'previous_year', pp: 'previous_period' }
const COMPARE_PARAM: Record<ComparisonMode, string> = { previous_year: 'py', previous_period: 'pp' }

export function buildPresets(months: string[], fiscalYears: number[]): PeriodPreset[] {
  const last = months[months.length - 1]
  const first = months[0]
  if (!last || !first) return []
  const available = new Set(months)
  const presets: PeriodPreset[] = []

  for (const year of [...fiscalYears].reverse()) {
    const start = `${year}-01`
    const end = `${year}-12`
    if (available.has(start) && available.has(end)) {
      presets.push({ id: `fy${year}`, label: `FY ${year}`, start, end })
    }
  }
  for (const count of [12, 6, 3]) {
    const start = months[months.length - count]
    if (start) presets.push({ id: `last${count}`, label: `Last ${count} months`, start, end: last })
  }
  presets.push({ id: 'all', label: 'All time', start: first, end: last })
  return presets
}

export function resolveFilters(
  params: URLSearchParams,
  dimensions: DimensionsResponse,
  presets: PeriodPreset[],
): FilterState {
  const months = dimensions.period.months
  const fallback = presets[0] ?? { start: months[0] ?? '', end: months[months.length - 1] ?? '' }

  const from = params.get('from')
  const to = params.get('to')
  const validRange = from && to && months.includes(from) && months.includes(to) && from <= to
  const knownUnits = dimensions.business_units.map((unit) => unit.code)
  const requested = (params.get('bu') ?? '').split(',').filter((code) => knownUnits.includes(code))
  // Selecting every unit is the same as not filtering.
  const units = requested.length === knownUnits.length ? [] : knownUnits.filter((c) => requested.includes(c))

  return {
    start: validRange ? from : fallback.start,
    end: validRange ? to : fallback.end,
    units,
    compare: COMPARE_CODES[params.get('cmp') ?? ''] ?? 'previous_year',
  }
}

export function FiltersProvider({
  dimensions,
  children,
}: {
  dimensions: DimensionsResponse
  children: ReactNode
}) {
  const [params, setParams] = useSearchParams()

  const presets = useMemo(
    () => buildPresets(dimensions.period.months, dimensions.period.fiscal_years),
    [dimensions],
  )
  const state = useMemo(() => resolveFilters(params, dimensions, presets), [params, dimensions, presets])

  // The URL updates asynchronously. Changes are applied on top of the latest requested
  // state, not the last rendered one, so two quick selections never overwrite each other.
  const latest = useRef(state)
  useEffect(() => {
    latest.current = state
  }, [state])

  const update = useCallback(
    (changes: Partial<FilterState> | ((current: FilterState) => Partial<FilterState>)) => {
      const current = latest.current
      const next = { ...current, ...(typeof changes === 'function' ? changes(current) : changes) }
      latest.current = next
      const search = new URLSearchParams()
      const isDefaultPeriod = presets[0] && next.start === presets[0].start && next.end === presets[0].end
      if (!isDefaultPeriod) {
        search.set('from', next.start)
        search.set('to', next.end)
      }
      if (next.units.length > 0) search.set('bu', next.units.join(','))
      if (next.compare !== 'previous_year') search.set('cmp', COMPARE_PARAM[next.compare])
      setParams(search, { replace: false })
    },
    [presets, setParams],
  )

  const value = useMemo<FiltersContextValue>(() => {
    const search = params.toString()
    return {
      ...state,
      dimensions,
      presets,
      activePreset: presets.find((p) => p.start === state.start && p.end === state.end) ?? null,
      apiParams: {
        start: state.start,
        end: state.end,
        business_unit: state.units,
        compare: state.compare,
      },
      search: search ? `?${search}` : '',
      setPeriod: (start, end) => update(start <= end ? { start, end } : { start: end, end: start }),
      toggleUnit: (code, selected) =>
        update((current) => {
          const known = dimensions.business_units.map((unit) => unit.code)
          const chosen = selected ? [...current.units, code] : current.units.filter((item) => item !== code)
          return { units: known.filter((item) => chosen.includes(item)) }
        }),
      setUnits: (units) => update({ units }),
      setCompare: (compare) => update({ compare }),
      reset: () => setParams(new URLSearchParams()),
    }
  }, [state, dimensions, presets, params, update, setParams])

  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>
}

export function useFilters(): FiltersContextValue {
  const context = useContext(FiltersContext)
  if (!context) throw new Error('useFilters must be used inside <FiltersProvider>')
  return context
}

export function comparisonLabel(compare: ComparisonMode): string {
  return compare === 'previous_year' ? 'prior year' : 'prior period'
}
