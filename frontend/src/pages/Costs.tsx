import { useMemo, useState } from 'react'

import { EChart } from '@/components/charts/EChart'
import { linesOption } from '@/components/charts/options'
import { ExportButton, Segmented } from '@/components/common/controls'
import { DataTable, type Column } from '@/components/common/DataTable'
import { Delta, directionOf, StatusBadge } from '@/components/common/Delta'
import { ChartPanel, Legend, Panel } from '@/components/common/Panel'
import { isStale, QueryBoundary } from '@/components/common/QueryBoundary'
import { RankedBars } from '@/components/common/RankedBars'
import { StatStrip, type Stat } from '@/components/common/StatStrip'
import type { ExpenseMatrixResponse, ExpenseRow, Kpi } from '@/lib/api'
import { sequentialColor, sequentialInk } from '@/lib/chart-theme'
import { comparisonLabel, useFilters } from '@/lib/filters'
import {
  formatChange,
  formatCurrency,
  formatCurrencyFull,
  formatMonth,
  formatPercent,
  formatSignedCurrencyFull,
  formatSignedPercent,
} from '@/lib/format'
import { useExpenseBreakdown, useExpenseMatrix, useKpis, useTimeSeries } from '@/lib/queries'
import { cn } from '@/lib/utils'

const DIRECT_COST_COLOR = '#3987e5'
const OPEX_COLOR = '#c98500'

// --------------------------------------------------------------------------- //
// Summary
// --------------------------------------------------------------------------- //
function kpiDelta(kpi: Kpi, basis: 'comparison' | 'budget') {
  const change = basis === 'comparison' ? kpi.change : kpi.budget_variance
  const changePct = basis === 'comparison' ? kpi.change_pct : kpi.budget_variance_pct
  const status = basis === 'comparison' ? kpi.comparison_status : kpi.budget_status
  if (change == null) return <span className="text-subtle">No data</span>
  return <Delta text={formatChange(change, changePct, kpi.unit)} direction={directionOf(change)} status={status} />
}

function CostSummary() {
  const kpis = useKpis()
  const { compare } = useFilters()
  const stats = useMemo<Stat[] | undefined>(() => {
    const find = (id: string) => kpis.data?.kpis.find((kpi) => kpi.id === id)
    const revenue = find('net_revenue')
    const direct = find('direct_costs')
    const opex = find('operating_expenses')
    if (!revenue || !direct || !opex || !revenue.value) return undefined
    const ratio = (value: number | null) => formatPercent(value == null ? null : value / revenue.value!)
    return [
      {
        label: 'Direct costs',
        value: formatCurrency(direct.value),
        detail: (
          <span className="flex items-center gap-1.5">
            {kpiDelta(direct, 'comparison')} vs {comparisonLabel(compare)}
          </span>
        ),
      },
      { label: 'Direct costs / revenue', value: ratio(direct.value), detail: `Budget ${ratio(direct.budget_value ?? null)}` },
      {
        label: 'Operating expenses',
        value: formatCurrency(opex.value),
        detail: <span className="flex items-center gap-1.5">{kpiDelta(opex, 'budget')} vs budget</span>,
      },
      { label: 'Opex / revenue', value: ratio(opex.value), detail: `Budget ${ratio(opex.budget_value ?? null)}` },
    ]
  }, [kpis.data, compare])
  return <StatStrip label="Cost summary" stats={stats} stale={isStale(kpis)} />
}

// --------------------------------------------------------------------------- //
// Cost ratios over time
// --------------------------------------------------------------------------- //
function CostRatioPanel() {
  const series = useTimeSeries()
  const { months, direct, opex, option } = useMemo(() => {
    const points = series.data?.points ?? []
    const ratio = (cost: number, revenue: number) => (revenue ? cost / revenue : null)
    const months = points.map((point) => point.month)
    const direct = points.map((p) => ratio(p.direct_costs, p.net_revenue))
    const opex = points.map((p) => ratio(p.operating_expenses, p.net_revenue))
    const option = linesOption(
      months,
      [
        { label: 'Direct costs / revenue', color: DIRECT_COST_COLOR, values: direct },
        { label: 'Operating expenses / revenue', color: OPEX_COLOR, values: opex },
      ],
      'percent',
    )
    return { months, direct, opex, option }
  }, [series.data])
  return (
    <ChartPanel
      title="Cost-to-revenue ratios"
      description="How much of each revenue dollar goes to goods and to operations"
      className="xl:col-span-2"
      stale={isStale(series)}
      legend={
        <Legend
          items={[
            { label: 'Direct costs / revenue', color: DIRECT_COST_COLOR, mark: 'line' },
            { label: 'Operating expenses / revenue', color: OPEX_COLOR, mark: 'line' },
          ]}
        />
      }
      table={{
        columns: ['Month', 'Direct costs / revenue', 'Operating expenses / revenue'],
        rows: months.map((month, index) => [formatMonth(month), formatPercent(direct[index]), formatPercent(opex[index])]),
      }}
    >
      <QueryBoundary query={series} minHeight={300} isEmpty={(data) => data.points.length === 0}>
        {() => <EChart option={option} height={300} ariaLabel="Direct costs and operating expenses as a share of net revenue by month" />}
      </QueryBoundary>
    </ChartPanel>
  )
}

function BehaviorPanel() {
  const behavior = useExpenseBreakdown('cost_behavior')
  return (
    <Panel
      title="Expenses by cost behavior"
      description="How operating expenses react to sales volume"
      stale={isStale(behavior)}
    >
      <QueryBoundary query={behavior} minHeight={300} isEmpty={(data) => data.rows.length === 0}>
        {(data) => (
          <div className="flex h-full flex-col">
            <RankedBars
              fill
              label="Operating expenses by cost behavior"
              color="#5c6f92"
              rows={data.rows.map((row) => ({
                key: row.key,
                label: row.label,
                value: row.actual,
                valueText: formatCurrency(row.actual),
                detail: formatPercent(row.share),
              }))}
            />
            <p className="mt-4 border-t pt-3 text-[11px] leading-relaxed text-subtle">
              Fixed costs do not follow sales; variable costs do; discretionary costs are management decisions.
            </p>
          </div>
        )}
      </QueryBoundary>
    </Panel>
  )
}

// --------------------------------------------------------------------------- //
// Breakdown with a switchable grouping
// --------------------------------------------------------------------------- //
type Grouping = 'account_group' | 'account' | 'cost_center'

const GROUPINGS: { value: Grouping; label: string }[] = [
  { value: 'account_group', label: 'Group' },
  { value: 'account', label: 'Account' },
  { value: 'cost_center', label: 'Cost center' },
]

function BreakdownPanel() {
  const [grouping, setGrouping] = useState<Grouping>('account_group')
  const breakdown = useExpenseBreakdown(grouping)
  const hasBudget = grouping !== 'cost_center'
  return (
    <Panel
      title="Where operating expenses go"
      description={hasBudget ? 'Amount and share of the total · tick: budget' : 'Amount and share of the total (no budget by cost center)'}
      className="xl:col-span-2"
      stale={isStale(breakdown)}
      actions={<Segmented label="Group expenses by" value={grouping} options={GROUPINGS} onChange={setGrouping} />}
    >
      <QueryBoundary query={breakdown} minHeight={340} isEmpty={(data) => data.rows.length === 0}>
        {(data) => (
          <RankedBars
            label="Operating expenses"
            color="#5c6f92"
            markerLabel="Budget"
            rows={data.rows.map((row) => ({
              key: row.key,
              label: row.label,
              value: row.actual,
              valueText: formatCurrency(row.actual),
              detail: formatPercent(row.share),
              marker: row.budget,
            }))}
          />
        )}
      </QueryBoundary>
    </Panel>
  )
}

// --------------------------------------------------------------------------- //
// Cost centre x account group heatmap (an HTML table: readable without colour)
// --------------------------------------------------------------------------- //
function Heatmap({ data }: { data: ExpenseMatrixResponse }) {
  const amount = new Map(data.cells.map((cell) => [`${cell.cost_center_name}|${cell.account_group}`, cell.amount]))
  const max = Math.max(1, ...data.cells.map((cell) => cell.amount))
  return (
    <div className="scrollbar-thin overflow-x-auto">
      <table className="w-full border-separate border-spacing-[2px] text-xs" aria-label="Operating expenses by cost center and account group">
        <thead>
          <tr>
            <th scope="col" className="px-2 py-1.5 text-left align-bottom font-medium text-muted-foreground">Expense group</th>
            {data.cost_centers.map((center) => (
              <th key={center} scope="col" className="w-[13%] min-w-[64px] px-1 py-1.5 text-center align-bottom text-[11px] leading-tight font-medium text-muted-foreground">
                {center}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.account_groups.map((group) => (
            <tr key={group}>
              <th scope="row" className="px-2 py-1.5 text-left font-medium whitespace-nowrap text-foreground">{group}</th>
              {data.cost_centers.map((center) => {
                const value = amount.get(`${center}|${group}`)
                const share = value ? value / max : 0
                return (
                  <td
                    key={center}
                    className={cn('tabular h-9 rounded-[4px] px-1 text-center', !value && 'text-subtle')}
                    style={
                      value
                        ? { backgroundColor: sequentialColor(share), color: sequentialInk(share) }
                        : { backgroundColor: 'var(--muted)' }
                    }
                    title={value ? `${center} · ${group}: ${formatCurrencyFull(value)}` : `${center} · ${group}: no expenses`}
                  >
                    {value ? formatCurrency(value) : '·'}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3 flex items-center gap-2 text-[11px] text-muted-foreground" aria-hidden>
        Lower
        <span className="flex h-2 w-40 overflow-hidden rounded-full">
          {[0.05, 0.2, 0.35, 0.5, 0.65, 0.8, 0.95].map((share) => (
            <span key={share} className="flex-1" style={{ backgroundColor: sequentialColor(share) }} />
          ))}
        </span>
        Higher
      </div>
    </div>
  )
}

function MatrixPanel() {
  const matrix = useExpenseMatrix()
  return (
    <Panel
      title="Expense groups by cost center"
      description="Brighter cells are larger amounts; every value is printed"
      className="xl:col-span-3"
      stale={isStale(matrix)}
    >
      <QueryBoundary query={matrix} minHeight={340} isEmpty={(data) => data.cells.length === 0}>
        {(data) => <Heatmap data={data} />}
      </QueryBoundary>
    </Panel>
  )
}

// --------------------------------------------------------------------------- //
// Account table
// --------------------------------------------------------------------------- //
function AccountsPanel() {
  const accounts = useExpenseBreakdown('account')
  const { compare } = useFilters()
  const columns: Column<ExpenseRow>[] = [
    {
      key: 'label',
      header: 'Account',
      sortValue: (row) => row.label,
      render: (row) => (
        <span className="flex items-baseline gap-2">
          <span className="font-medium text-foreground">{row.label}</span>
          {row.key !== 'total' ? <span className="text-[11px] text-subtle">{row.key}</span> : null}
        </span>
      ),
    },
    { key: 'actual', header: 'Actual', align: 'right', sortValue: (row) => row.actual, render: (row) => formatCurrencyFull(row.actual) },
    { key: 'budget', header: 'Budget', align: 'right', sortValue: (row) => row.budget, render: (row) => formatCurrencyFull(row.budget) },
    { key: 'variance', header: 'Variance', align: 'right', sortValue: (row) => row.variance, render: (row) => formatSignedCurrencyFull(row.variance) },
    { key: 'variance_pct', header: 'Var. %', align: 'right', sortValue: (row) => row.variance_pct, render: (row) => formatSignedPercent(row.variance_pct) },
    { key: 'status', header: 'Status', sortValue: (row) => row.status, render: (row) => (row.status ? <StatusBadge status={row.status} /> : '—') },
    { key: 'pct_of_revenue', header: '% of revenue', align: 'right', sortValue: (row) => row.pct_of_revenue, render: (row) => formatPercent(row.pct_of_revenue) },
    {
      key: 'change',
      header: `vs ${comparisonLabel(compare)}`,
      align: 'right',
      sortValue: (row) => row.change_pct,
      render: (row) =>
        row.change_pct == null ? (
          '—'
        ) : (
          <Delta
            text={formatSignedPercent(row.change_pct)}
            direction={directionOf(row.change_pct)}
            // For an expense, growing is unfavorable.
            status={Math.abs(row.change_pct) < 0.005 ? 'on_target' : row.change_pct > 0 ? 'unfavorable' : 'favorable'}
          />
        ),
    },
  ]
  return (
    <Panel
      title="Expense accounts"
      description="Actual against budget for every operating-expense account"
      stale={isStale(accounts)}
      actions={<ExportButton dataset="expenses-by-cost-center" label="Export detail" />}
    >
      <QueryBoundary query={accounts} minHeight={360} isEmpty={(data) => data.rows.length === 0}>
        {(data) => (
          <DataTable
            label="Operating expense accounts"
            columns={columns}
            rows={data.rows}
            rowKey={(row) => row.key}
            footer={data.total}
            initialSort={{ key: 'actual', direction: 'desc' }}
            dense
          />
        )}
      </QueryBoundary>
    </Panel>
  )
}

export default function Costs() {
  return (
    <div className="space-y-4">
      <CostSummary />
      <div className="grid gap-4 xl:grid-cols-3">
        <CostRatioPanel />
        <BehaviorPanel />
      </div>
      <div className="grid gap-4 xl:grid-cols-5">
        <BreakdownPanel />
        <MatrixPanel />
      </div>
      <AccountsPanel />
    </div>
  )
}
