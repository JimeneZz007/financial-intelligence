import { ArrowRight, CircleDollarSign, Landmark, Package, Percent } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'

import { EChart } from '@/components/charts/EChart'
import { evolutionOption, type EvolutionPoint } from '@/components/charts/options'
import { ExportButton, Segmented } from '@/components/common/controls'
import { DataTable, Pagination, type Column, type SortState } from '@/components/common/DataTable'
import { Delta, directionOf } from '@/components/common/Delta'
import { InsightList } from '@/components/common/InsightList'
import { KpiTile, KpiTileSkeleton } from '@/components/common/KpiTile'
import { ChartPanel, Legend, Panel } from '@/components/common/Panel'
import { isStale, QueryBoundary } from '@/components/common/QueryBoundary'
import { RankedBars } from '@/components/common/RankedBars'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { MonthlyRecord, StatementLine, TimeSeriesPoint } from '@/lib/api'
import { chartColors, unitColor } from '@/lib/chart-theme'
import { comparisonLabel, useFilters } from '@/lib/filters'
import {
  formatByUnit,
  formatCurrency,
  formatCurrencyFull,
  formatMonth,
  formatPercent,
  formatSignedPercent,
  type Unit,
} from '@/lib/format'
import {
  useBudgetStatement,
  useBudgetVariance,
  useExpenseBreakdown,
  useInsights,
  useKpis,
  useMonthlyRecords,
  useProfitability,
  useTimeSeries,
  type RecordsQuery,
} from '@/lib/queries'
import { cn } from '@/lib/utils'

const HEADLINE_KPIS = [
  { id: 'net_revenue', icon: CircleDollarSign },
  { id: 'direct_costs', icon: Package },
  { id: 'operating_income', icon: Landmark },
  { id: 'operating_margin', icon: Percent },
] as const

// --------------------------------------------------------------------------- //
// KPI row
// --------------------------------------------------------------------------- //
function KpiRow() {
  const kpis = useKpis()
  const { compare } = useFilters()
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" data-testid="kpi-row">
      {HEADLINE_KPIS.map(({ id, icon }) => {
        const kpi = kpis.data?.kpis.find((item) => item.id === id)
        if (!kpi) return <KpiTileSkeleton key={id} />
        return <KpiTile key={id} kpi={kpi} icon={icon} comparisonLabel={comparisonLabel(compare)} stale={isStale(kpis)} />
      })}
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Financial evolution
// --------------------------------------------------------------------------- //
type EvolutionMetric = 'net_revenue' | 'gross_profit' | 'operating_income' | 'operating_margin'

const EVOLUTION_METRICS: { value: EvolutionMetric; label: string; unit: Unit }[] = [
  { value: 'net_revenue', label: 'Net revenue', unit: 'currency' },
  { value: 'gross_profit', label: 'Gross profit', unit: 'currency' },
  { value: 'operating_income', label: 'Operating income', unit: 'currency' },
  { value: 'operating_margin', label: 'Operating margin', unit: 'percent' },
]

function evolutionPoint(point: TimeSeriesPoint, metric: EvolutionMetric): EvolutionPoint {
  const yoy = (value: number | null) => (value == null ? undefined : `${formatSignedPercent(value)} vs prior year`)
  switch (metric) {
    case 'net_revenue':
      return { month: point.month, actual: point.net_revenue, budget: point.budget_net_revenue, note: yoy(point.revenue_yoy_pct) }
    case 'gross_profit':
      return {
        month: point.month,
        actual: point.gross_profit,
        budget: point.budget_net_revenue - point.budget_direct_costs,
      }
    case 'operating_income':
      return {
        month: point.month,
        actual: point.operating_income,
        budget: point.budget_operating_income,
        note: yoy(point.operating_income_yoy_pct),
      }
    case 'operating_margin':
      return {
        month: point.month,
        actual: point.operating_margin,
        budget: point.budget_net_revenue ? point.budget_operating_income / point.budget_net_revenue : null,
      }
  }
}

function EvolutionPanel() {
  const series = useTimeSeries()
  const [metric, setMetric] = useState<EvolutionMetric>('net_revenue')
  const spec = EVOLUTION_METRICS.find((item) => item.value === metric)!
  const points = useMemo(
    () => (series.data?.points ?? []).map((point) => evolutionPoint(point, metric)),
    [series.data, metric],
  )
  const option = useMemo(
    () => evolutionOption(points, spec.unit, { actual: 'Actual', budget: 'Budget' }),
    [points, spec.unit],
  )
  return (
    <ChartPanel
      title="Financial evolution"
      description={`Monthly ${spec.label.toLowerCase()}: actual against budget`}
      className="xl:col-span-2"
      stale={isStale(series)}
      actions={<Segmented label="Metric" value={metric} options={EVOLUTION_METRICS} onChange={setMetric} />}
      legend={
        <Legend
          items={[
            { label: 'Actual', color: chartColors.series, mark: 'bar' },
            { label: 'Budget', color: chartColors.budget, mark: 'line' },
          ]}
        />
      }
      table={{
        columns: ['Month', 'Actual', 'Budget'],
        rows: points.map((p) => [formatMonth(p.month), formatByUnit(p.actual, spec.unit), formatByUnit(p.budget, spec.unit)]),
      }}
    >
      <QueryBoundary query={series} minHeight={336} isEmpty={(data) => data.points.length === 0}>
        {() => <EChart option={option} height={336} ariaLabel={`${spec.label} by month, actual versus budget`} />}
      </QueryBoundary>
    </ChartPanel>
  )
}

// --------------------------------------------------------------------------- //
// Budget vs actual (P&L lines against plan)
// --------------------------------------------------------------------------- //
const PLAN_LINES: { key: string; label: string }[] = [
  { key: '4000', label: 'Net revenue' },
  { key: '5000', label: 'Direct costs' },
  { key: 'gross_profit', label: 'Gross profit' },
  { key: 'operating_expenses', label: 'Operating expenses' },
  { key: 'operating_income', label: 'Operating income' },
]

const STATUS_FILL: Record<StatementLine['status'], string> = {
  favorable: 'var(--favorable)',
  unfavorable: 'var(--unfavorable)',
  on_target: 'var(--series)',
}

function PlanLine({ line, label }: { line: StatementLine; label: string }) {
  const scale = Math.max(line.actual, line.budget, 1) * 1.08
  return (
    <li>
      <div className="flex items-center justify-between gap-3">
        <span className="text-[13px] font-medium text-foreground">{label}</span>
        <Delta
          text={formatSignedPercent(line.variance_pct)}
          direction={directionOf(line.variance)}
          status={line.status}
          className="text-xs"
        />
      </div>
      {/* Bullet: the bar is the actual amount, the tick marks the budget. */}
      <div className="relative mt-2 h-2 rounded-r-[4px] bg-track">
        <div
          className="h-full rounded-r-[4px] transition-[width] duration-300"
          style={{ width: `${(Math.max(line.actual, 0) / scale) * 100}%`, backgroundColor: STATUS_FILL[line.status] }}
        />
        <span
          aria-hidden
          className="absolute -top-1 h-4 w-0.5 rounded-full bg-foreground/85"
          style={{ left: `calc(${(line.budget / scale) * 100}% - 1px)` }}
        />
      </div>
      <p className="tabular mt-1.5 flex justify-between text-[11px] text-muted-foreground">
        <span>Actual {formatCurrency(line.actual)}</span>
        <span>Budget {formatCurrency(line.budget)}</span>
      </p>
    </li>
  )
}

function PlanPanel() {
  const statement = useBudgetStatement()
  return (
    <Panel
      title="Budget vs actual"
      description="Bar: actual · tick: budget"
      stale={isStale(statement)}
      actions={
        <Link to="/budget" className="inline-flex items-center gap-1 text-xs font-medium text-brand hover:underline">
          Details <ArrowRight aria-hidden className="size-3" />
        </Link>
      }
    >
      <QueryBoundary query={statement} minHeight={300}>
        {(data) => (
          <ul className="space-y-4" aria-label="Income statement lines against budget">
            {PLAN_LINES.map(({ key, label }) => {
              const line = data.lines.find((item) => item.key === key)
              return line ? <PlanLine key={key} line={line} label={label} /> : null
            })}
          </ul>
        )}
      </QueryBoundary>
    </Panel>
  )
}

// --------------------------------------------------------------------------- //
// Breakdown of revenue and expenses
// --------------------------------------------------------------------------- //
function RevenueBreakdownPanel() {
  const categories = useProfitability('category')
  return (
    <Panel
      title="Revenue by category"
      description="Net revenue and share of the total"
      stale={isStale(categories)}
      actions={
        <Link to="/revenue" className="inline-flex items-center gap-1 text-xs font-medium text-brand hover:underline">
          Details <ArrowRight aria-hidden className="size-3" />
        </Link>
      }
    >
      <QueryBoundary query={categories} minHeight={240} isEmpty={(data) => data.rows.length === 0}>
        {(data) => (
          <RankedBars
            fill
            label="Net revenue by product category"
            rows={data.rows.map((row) => ({
              key: row.key,
              label: row.label,
              value: row.net_revenue,
              valueText: formatCurrency(row.net_revenue),
              detail: formatPercent(row.revenue_share),
            }))}
          />
        )}
      </QueryBoundary>
    </Panel>
  )
}

function ExpenseBreakdownPanel() {
  const groups = useExpenseBreakdown('account_group')
  return (
    <Panel
      title="Operating expenses by group"
      description="Amount and share of net revenue · tick: budget"
      stale={isStale(groups)}
      actions={
        <Link to="/costs" className="inline-flex items-center gap-1 text-xs font-medium text-brand hover:underline">
          Details <ArrowRight aria-hidden className="size-3" />
        </Link>
      }
    >
      <QueryBoundary query={groups} minHeight={240} isEmpty={(data) => data.rows.length === 0}>
        {(data) => (
          <RankedBars
            label="Operating expenses by account group"
            color="#5c6f92"
            markerLabel="Budget"
            rows={data.rows.map((row) => ({
              key: row.key,
              label: row.label,
              value: row.actual,
              valueText: formatCurrency(row.actual),
              detail: `${formatPercent(row.pct_of_revenue)} of revenue`,
              marker: row.budget,
            }))}
          />
        )}
      </QueryBoundary>
    </Panel>
  )
}

// --------------------------------------------------------------------------- //
// Business unit comparison
// --------------------------------------------------------------------------- //
interface UnitRow {
  key: string
  label: string
  revenue: number
  share: number | null
  grossMargin: number | null
  operatingIncome: number | null
  operatingMargin: number | null
  revenueVariancePct: number | null
  revenueStatus: StatementLine['status'] | null
}

function UnitsPanel() {
  const profitability = useProfitability('business_unit')
  const variance = useBudgetVariance('business_unit')

  const rows = useMemo<UnitRow[]>(() => {
    if (!profitability.data) return []
    return profitability.data.rows.map((row) => {
      const budget = variance.data?.rows.find((item) => item.key === row.key)
      return {
        key: row.key,
        label: row.label,
        revenue: row.net_revenue,
        share: row.revenue_share ?? null,
        grossMargin: row.gross_margin ?? null,
        operatingIncome: row.operating_income ?? null,
        operatingMargin: row.operating_margin ?? null,
        revenueVariancePct: budget?.net_revenue.variance_pct ?? null,
        revenueStatus: budget?.net_revenue.status ?? null,
      }
    })
  }, [profitability.data, variance.data])

  const maxRevenue = Math.max(1, ...rows.map((row) => row.revenue))
  const columns: Column<UnitRow>[] = [
    {
      key: 'unit',
      header: 'Business unit',
      sortValue: (row) => row.label,
      render: (row) => (
        <span className="flex items-center gap-2 font-medium text-foreground">
          <span aria-hidden className="size-2 rounded-[2px]" style={{ backgroundColor: unitColor(row.key) }} />
          {row.label}
        </span>
      ),
    },
    {
      key: 'revenue',
      header: 'Net revenue',
      align: 'right',
      sortValue: (row) => row.revenue,
      render: (row) => (
        <span className="inline-flex items-center justify-end gap-2.5">
          <span aria-hidden className="hidden h-1.5 w-20 overflow-hidden rounded-r-[3px] bg-track sm:block">
            <span
              className="block h-full rounded-r-[3px]"
              style={{ width: `${(row.revenue / maxRevenue) * 100}%`, backgroundColor: unitColor(row.key) }}
            />
          </span>
          {formatCurrency(row.revenue)}
        </span>
      ),
    },
    { key: 'share', header: 'Share', align: 'right', sortValue: (row) => row.share, render: (row) => formatPercent(row.share) },
    {
      key: 'gross_margin',
      header: 'Gross margin',
      align: 'right',
      sortValue: (row) => row.grossMargin,
      render: (row) => formatPercent(row.grossMargin),
    },
    {
      key: 'operating_income',
      header: 'Operating income',
      align: 'right',
      sortValue: (row) => row.operatingIncome,
      render: (row) => formatCurrency(row.operatingIncome),
    },
    {
      key: 'operating_margin',
      header: 'Op. margin',
      align: 'right',
      sortValue: (row) => row.operatingMargin,
      render: (row) => formatPercent(row.operatingMargin),
    },
    {
      key: 'vs_budget',
      header: 'Revenue vs budget',
      align: 'right',
      sortValue: (row) => row.revenueVariancePct,
      render: (row) =>
        row.revenueVariancePct == null ? (
          '—'
        ) : (
          <Delta
            text={formatSignedPercent(row.revenueVariancePct)}
            direction={directionOf(row.revenueVariancePct)}
            status={row.revenueStatus}
          />
        ),
    },
  ]

  return (
    <Panel
      title="Business units"
      description="Size, profitability and revenue against budget"
      stale={isStale(profitability) || isStale(variance)}
    >
      <QueryBoundary query={profitability} minHeight={220} isEmpty={(data) => data.rows.length === 0}>
        {() => (
          <DataTable
            label="Business unit comparison"
            columns={columns}
            rows={rows}
            rowKey={(row) => row.key}
            initialSort={{ key: 'revenue', direction: 'desc' }}
          />
        )}
      </QueryBoundary>
    </Panel>
  )
}

// --------------------------------------------------------------------------- //
// Analytical table (server-side sorting, filtering and pagination)
// --------------------------------------------------------------------------- //
const PAGE_SIZE = 12

const RECORD_COLUMNS: Column<MonthlyRecord>[] = [
  { key: 'month', header: 'Month', sortValue: (row) => row.month, render: (row) => formatMonth(row.month) },
  {
    key: 'business_unit_name',
    header: 'Business unit',
    sortValue: (row) => row.business_unit_name,
    render: (row) => (
      <span className="flex items-center gap-2">
        <span aria-hidden className="size-2 rounded-[2px]" style={{ backgroundColor: unitColor(row.business_unit_code) }} />
        {row.business_unit_name}
      </span>
    ),
  },
  {
    key: 'net_revenue',
    header: 'Net revenue',
    align: 'right',
    sortValue: (row) => row.net_revenue,
    render: (row) => formatCurrencyFull(row.net_revenue),
  },
  {
    key: 'gross_margin',
    header: 'Gross margin',
    align: 'right',
    sortValue: (row) => row.gross_margin,
    render: (row) => formatPercent(row.gross_margin),
  },
  {
    key: 'operating_expenses',
    header: 'Opex',
    align: 'right',
    title: 'Operating expenses',
    sortValue: (row) => row.operating_expenses,
    render: (row) => formatCurrencyFull(row.operating_expenses),
  },
  {
    key: 'operating_income',
    header: 'Operating income',
    align: 'right',
    sortValue: (row) => row.operating_income,
    render: (row) => (
      <span className={cn(row.operating_income < 0 && 'text-unfavorable-text')}>{formatCurrencyFull(row.operating_income)}</span>
    ),
  },
  {
    key: 'operating_margin',
    header: 'Op. margin',
    align: 'right',
    sortValue: (row) => row.operating_margin,
    render: (row) => formatPercent(row.operating_margin),
  },
  {
    key: 'revenue_variance_pct',
    header: 'Revenue vs budget',
    align: 'right',
    sortValue: (row) => row.revenue_variance_pct,
    render: (row) => (
      <Delta
        text={formatSignedPercent(row.revenue_variance_pct)}
        direction={directionOf(row.revenue_variance_pct)}
        status={
          row.revenue_variance_pct == null || Math.abs(row.revenue_variance_pct) < 0.005
            ? 'on_target'
            : row.revenue_variance_pct > 0
              ? 'favorable'
              : 'unfavorable'
        }
      />
    ),
  },
]

function RecordsPanel() {
  const { apiParams } = useFilters()
  const scope = JSON.stringify(apiParams)
  const [state, setState] = useState<RecordsQuery & { scope: string }>({
    scope,
    page: 1,
    pageSize: PAGE_SIZE,
    sortBy: 'month',
    sortDir: 'desc',
    revenueVsBudget: 'all',
  })
  // A new slice of data starts again from the first page: the stored page only counts
  // while the global filters it was chosen under are still the active ones.
  const query: RecordsQuery = { ...state, page: state.scope === scope ? state.page : 1 }
  const setQuery = (update: (current: RecordsQuery) => RecordsQuery) =>
    setState((current) => ({ ...update({ ...current, page: current.scope === scope ? current.page : 1 }), scope }))
  const records = useMonthlyRecords(query)

  const sort: SortState = { key: query.sortBy, direction: query.sortDir }
  return (
    <Panel
      title="Monthly results"
      description="One row per month and business unit"
      stale={isStale(records)}
      actions={
        <>
          <Select
            value={query.revenueVsBudget}
            onValueChange={(value) =>
              setQuery((current) => ({ ...current, page: 1, revenueVsBudget: value as RecordsQuery['revenueVsBudget'] }))
            }
          >
            <SelectTrigger size="sm" className="h-7 text-xs" aria-label="Filter rows by revenue against budget" data-testid="records-filter">
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="end">
              <SelectItem value="all" className="text-xs">All months</SelectItem>
              <SelectItem value="above" className="text-xs">Revenue above budget</SelectItem>
              <SelectItem value="below" className="text-xs">Revenue below budget</SelectItem>
            </SelectContent>
          </Select>
          <ExportButton dataset="monthly-pnl" />
        </>
      }
    >
      <QueryBoundary
        query={records}
        minHeight={360}
        isEmpty={(data) => data.rows.length === 0 && data.pagination.total_items === 0}
        emptyTitle="No months match this filter"
        emptyHint="Change the table filter or widen the period."
      >
        {(data) => (
          <>
            <DataTable
              label="Monthly results by business unit"
              columns={RECORD_COLUMNS}
              rows={data.rows}
              rowKey={(row) => `${row.month}-${row.business_unit_code}`}
              sort={sort}
              onSortChange={(next) =>
                setQuery((current) => ({ ...current, page: 1, sortBy: next.key, sortDir: next.direction }))
              }
              dense
            />
            <Pagination
              page={data.pagination.page}
              totalPages={data.pagination.total_pages}
              totalItems={data.pagination.total_items}
              pageSize={data.pagination.page_size}
              onPageChange={(page) => setQuery((current) => ({ ...current, page }))}
            />
          </>
        )}
      </QueryBoundary>
    </Panel>
  )
}

// --------------------------------------------------------------------------- //
// Findings
// --------------------------------------------------------------------------- //
function InsightsPanel() {
  const insights = useInsights()
  return (
    <Panel
      title="Key findings"
      description="Computed from the current selection"
      stale={isStale(insights)}
      actions={
        <Link to="/trends" className="inline-flex items-center gap-1 text-xs font-medium text-brand hover:underline">
          All findings <ArrowRight aria-hidden className="size-3" />
        </Link>
      }
    >
      <QueryBoundary
        query={insights}
        minHeight={240}
        isEmpty={(data) => data.insights.length === 0}
        emptyTitle="No findings for this selection"
      >
        {(data) => <InsightList insights={data.insights} limit={6} grid />}
      </QueryBoundary>
    </Panel>
  )
}

export default function Overview() {
  return (
    <div className="space-y-4">
      <KpiRow />
      <div className="grid gap-4 xl:grid-cols-3">
        <EvolutionPanel />
        <PlanPanel />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <RevenueBreakdownPanel />
        <ExpenseBreakdownPanel />
      </div>
      <UnitsPanel />
      <InsightsPanel />
      <RecordsPanel />
    </div>
  )
}
