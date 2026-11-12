import { useMemo, useState } from 'react'

import { EChart } from '@/components/charts/EChart'
import { signedColumnsOption, waterfallOption, type SignedColumn } from '@/components/charts/options'
import { ExportButton, Segmented } from '@/components/common/controls'
import { DataTable, type Column } from '@/components/common/DataTable'
import { Delta, directionOf, StatusBadge } from '@/components/common/Delta'
import { ChartPanel, Legend, Panel } from '@/components/common/Panel'
import { isStale, QueryBoundary } from '@/components/common/QueryBoundary'
import { StatStrip, type Stat } from '@/components/common/StatStrip'
import type { BudgetMatrixResponse, BudgetVarianceRow, Favorability, StatementLine } from '@/lib/api'
import { chartColors, divergingColor, unitColor } from '@/lib/chart-theme'
import {
  formatCurrency,
  formatCurrencyFull,
  formatPercent,
  formatSignedCurrency,
  formatSignedCurrencyFull,
  formatSignedPercent,
} from '@/lib/format'
import { useBridge, useBudgetMatrix, useBudgetStatement, useBudgetVariance } from '@/lib/queries'
import { cn } from '@/lib/utils'

type Measure = 'net_revenue' | 'operating_expenses' | 'operating_income'

const MEASURES: { value: Measure; label: string }[] = [
  { value: 'operating_income', label: 'Operating income' },
  { value: 'net_revenue', label: 'Net revenue' },
  { value: 'operating_expenses', label: 'Operating expenses' },
]

const favorableFlag = (status: Favorability): boolean | null =>
  status === 'on_target' ? null : status === 'favorable'

// --------------------------------------------------------------------------- //
// Summary
// --------------------------------------------------------------------------- //
function BudgetSummary() {
  const statement = useBudgetStatement()
  const stats = useMemo<Stat[] | undefined>(() => {
    const lines = statement.data?.lines
    if (!lines) return undefined
    const line = (key: string) => lines.find((item) => item.key === key)
    const revenue = line('4000')
    const opex = line('operating_expenses')
    const income = line('operating_income')
    if (!revenue || !opex || !income) return undefined
    const accounts = lines.filter((item) => item.level === 'account' && item.account_type === 'OPERATING_EXPENSE')
    const over = accounts.filter((item) => item.status === 'unfavorable').length
    const detail = (item: StatementLine) => (
      <span className="flex items-center gap-1.5">
        <Delta text={formatSignedCurrency(item.variance)} direction={directionOf(item.variance)} status={item.status} />
        vs budget
      </span>
    )
    return [
      {
        label: 'Revenue attainment',
        value: formatPercent(revenue.budget ? revenue.actual / revenue.budget : null),
        detail: detail(revenue),
      },
      {
        label: 'Operating income attainment',
        value: formatPercent(income.budget ? income.actual / income.budget : null),
        detail: detail(income),
      },
      {
        label: 'Operating expenses vs budget',
        value: formatSignedPercent(opex.variance_pct),
        detail: detail(opex),
      },
      {
        label: 'Expense accounts over budget',
        value: `${over} of ${accounts.length}`,
        detail: 'Variance above 0.5% of budget',
      },
    ]
  }, [statement.data])
  return <StatStrip label="Budget summary" stats={stats} stale={isStale(statement)} />
}

// --------------------------------------------------------------------------- //
// Variance by month
// --------------------------------------------------------------------------- //
function MonthlyVariancePanel() {
  const [measure, setMeasure] = useState<Measure>('operating_income')
  const variance = useBudgetVariance('month')
  const label = MEASURES.find((item) => item.value === measure)!.label
  const columns = useMemo<SignedColumn[]>(
    () =>
      (variance.data?.rows ?? []).map((row) => {
        const value = row[measure]
        return {
          label: row.label.replace(/ \d{4}$/, (year) => (variance.data!.rows.length > 12 ? ` ${year.trim().slice(2)}` : '')),
          value: value.variance,
          favorable: favorableFlag(value.status),
          detail: [
            { label: 'Actual', value: formatCurrency(value.actual) },
            { label: 'Budget', value: formatCurrency(value.budget), muted: true },
          ],
        }
      }),
    [variance.data, measure],
  )
  const option = useMemo(() => signedColumnsOption(columns), [columns])
  return (
    <ChartPanel
      title="Variance by month"
      description={`${label}: actual minus budget`}
      className="xl:col-span-2"
      stale={isStale(variance)}
      actions={<Segmented label="Measure" value={measure} options={MEASURES} onChange={setMeasure} />}
      legend={
        <Legend
          items={[
            { label: 'Favorable', color: chartColors.favorable },
            { label: 'Unfavorable', color: chartColors.unfavorable },
            { label: 'On target', color: chartColors.neutral },
          ]}
        />
      }
      table={{
        columns: ['Month', 'Actual', 'Budget', 'Variance', 'Variance %', 'Status'],
        rows: (variance.data?.rows ?? []).map((row) => [
          row.label,
          formatCurrency(row[measure].actual),
          formatCurrency(row[measure].budget),
          formatSignedCurrency(row[measure].variance),
          formatSignedPercent(row[measure].variance_pct),
          row[measure].status.replace('_', ' '),
        ]),
      }}
    >
      <QueryBoundary query={variance} minHeight={300} isEmpty={(data) => data.rows.length === 0}>
        {() => <EChart option={option} height={300} ariaLabel={`${label} variance against budget by month`} />}
      </QueryBoundary>
    </ChartPanel>
  )
}

// --------------------------------------------------------------------------- //
// Variance by business unit
// --------------------------------------------------------------------------- //
function UnitVariance({ row, scale }: { row: BudgetVarianceRow; scale: number }) {
  const income = row.operating_income
  const width = Math.min(50, (Math.abs(income.variance) / scale) * 50)
  return (
    <li>
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-2 text-[13px] font-medium text-foreground">
          <span aria-hidden className="size-2 rounded-[2px]" style={{ backgroundColor: unitColor(row.key) }} />
          {row.label}
        </span>
        <Delta
          text={formatSignedCurrency(income.variance)}
          direction={directionOf(income.variance)}
          status={income.status}
          className="text-xs"
        />
      </div>
      {/* Diverging bar around zero: right improves operating income, left reduces it. */}
      <div className="relative mt-2 h-2 rounded-full bg-track" aria-hidden>
        <span className="absolute inset-y-[-3px] left-1/2 w-px bg-foreground/50" />
        <span
          className="absolute inset-y-0 rounded-[3px]"
          style={{
            width: `${width}%`,
            left: income.variance >= 0 ? '50%' : `${50 - width}%`,
            backgroundColor:
              income.status === 'on_target'
                ? 'var(--subtle-foreground)'
                : income.status === 'favorable'
                  ? 'var(--favorable)'
                  : 'var(--unfavorable)',
          }}
        />
      </div>
      <p className="tabular mt-1.5 flex justify-between text-[11px] text-muted-foreground">
        <span>Revenue {formatSignedPercent(row.net_revenue.variance_pct)}</span>
        <span>Opex {formatSignedPercent(row.operating_expenses.variance_pct)}</span>
      </p>
    </li>
  )
}

function UnitVariancePanel() {
  const variance = useBudgetVariance('business_unit')
  return (
    <Panel
      title="Operating income vs budget"
      description="By business unit · bar: variance around zero"
      stale={isStale(variance)}
    >
      <QueryBoundary query={variance} minHeight={300} isEmpty={(data) => data.rows.length === 0}>
        {(data) => {
          const scale = Math.max(1, ...data.rows.map((row) => Math.abs(row.operating_income.variance)))
          return (
            <ul className="flex h-full flex-col justify-between gap-4" aria-label="Operating income variance by business unit">
              {data.rows.map((row) => (
                <UnitVariance key={row.key} row={row} scale={scale} />
              ))}
            </ul>
          )
        }}
      </QueryBoundary>
    </Panel>
  )
}

// --------------------------------------------------------------------------- //
// Bridge from budget to actual
// --------------------------------------------------------------------------- //
function BudgetBridgePanel() {
  const bridge = useBridge('budget')
  const option = useMemo(() => waterfallOption(bridge.data?.steps ?? []), [bridge.data])
  return (
    <ChartPanel
      title="From budgeted to actual operating income"
      description="Each step is the variance of one line, expressed as its effect on profit"
      stale={isStale(bridge)}
      legend={
        <Legend
          items={[
            { label: 'Operating income', color: chartColors.series },
            { label: 'Favorable variance', color: chartColors.favorable },
            { label: 'Unfavorable variance', color: chartColors.unfavorable },
          ]}
        />
      }
      table={{
        columns: ['Step', 'Amount'],
        rows: (bridge.data?.steps ?? []).map((step) => [
          step.label,
          step.kind === 'total' ? formatCurrency(step.amount) : formatSignedCurrency(step.amount),
        ]),
      }}
    >
      <QueryBoundary query={bridge} minHeight={320} isEmpty={(data) => data.steps.length === 0}>
        {() => <EChart option={option} height={320} ariaLabel="Bridge from budgeted to actual operating income" />}
      </QueryBoundary>
    </ChartPanel>
  )
}

// --------------------------------------------------------------------------- //
// Income statement
// --------------------------------------------------------------------------- //
function ImpactBar({ value, scale }: { value: number; scale: number }) {
  const width = Math.min(50, (Math.abs(value) / scale) * 50)
  return (
    <span className="relative inline-block h-2 w-20 rounded-full bg-track align-middle" aria-hidden>
      <span className="absolute inset-y-0 left-1/2 w-px bg-foreground/40" />
      <span
        className="absolute inset-y-0 rounded-[3px]"
        style={{
          width: `${width}%`,
          left: value >= 0 ? '50%' : `${50 - width}%`,
          backgroundColor: value >= 0 ? 'var(--favorable)' : 'var(--unfavorable)',
        }}
      />
    </span>
  )
}

function StatementPanel() {
  const statement = useBudgetStatement()
  const accounts = (statement.data?.lines ?? []).filter((line) => line.level === 'account')
  const scale = Math.max(1, ...accounts.map((line) => Math.abs(line.profit_impact)))
  const columns: Column<StatementLine>[] = [
    {
      key: 'label',
      header: 'Line',
      render: (line) =>
        line.level === 'subtotal' ? (
          <span className="text-foreground">{line.label}</span>
        ) : (
          <span className="flex items-baseline gap-2 pl-3">
            <span className="text-foreground/90">{line.label}</span>
            <span className="text-[11px] text-subtle">{line.key}</span>
          </span>
        ),
    },
    { key: 'actual', header: 'Actual', align: 'right', render: (line) => formatCurrencyFull(line.actual) },
    { key: 'budget', header: 'Budget', align: 'right', render: (line) => formatCurrencyFull(line.budget) },
    { key: 'variance', header: 'Variance', align: 'right', render: (line) => formatSignedCurrencyFull(line.variance) },
    { key: 'variance_pct', header: 'Var. %', align: 'right', render: (line) => formatSignedPercent(line.variance_pct) },
    { key: 'status', header: 'Status', render: (line) => <StatusBadge status={line.status} /> },
    {
      key: 'impact',
      header: 'Effect on operating income',
      align: 'right',
      title: 'The variance expressed as its effect on operating income',
      render: (line) => (
        <span className="inline-flex items-center justify-end gap-2.5">
          {line.level === 'account' ? <ImpactBar value={line.profit_impact} scale={scale} /> : null}
          <span className="w-20">{formatSignedCurrencyFull(line.profit_impact)}</span>
        </span>
      ),
    },
    { key: 'pct', header: '% of revenue', align: 'right', render: (line) => formatPercent(line.pct_of_revenue) },
  ]
  return (
    <Panel
      title="Income statement: actual vs budget"
      description="One line per account. The effects of the 13 accounts add up to the operating income variance"
      stale={isStale(statement)}
      actions={<ExportButton dataset="budget-by-account" label="Export detail" />}
    >
      <QueryBoundary query={statement} minHeight={420} isEmpty={(data) => data.lines.length === 0}>
        {(data) => (
          <DataTable
            label="Income statement, actual against budget"
            columns={columns}
            rows={data.lines}
            rowKey={(line) => line.key}
            emphasizedRow={(line) => line.level === 'subtotal'}
            dense
          />
        )}
      </QueryBoundary>
    </Panel>
  )
}

// --------------------------------------------------------------------------- //
// Business unit x account matrix
// --------------------------------------------------------------------------- //
/** Variance of +/-25% of budget or more is drawn at full intensity. */
const FULL_INTENSITY = 0.25

function VarianceMatrix({ data }: { data: BudgetMatrixResponse }) {
  const units = [...new Map(data.cells.map((cell) => [cell.business_unit_code, cell.business_unit_name])).entries()]
  const accounts = [...new Map(data.cells.map((cell) => [cell.account_code, cell.account_name])).entries()]
  const cellOf = new Map(data.cells.map((cell) => [`${cell.account_code}|${cell.business_unit_code}`, cell]))
  return (
    <div className="scrollbar-thin overflow-x-auto">
      <table className="w-full border-separate border-spacing-[2px] text-xs" aria-label="Budget variance by account and business unit">
        <thead>
          <tr>
            <th scope="col" className="px-2 py-1.5 text-left font-medium text-muted-foreground">Account</th>
            {units.map(([code, name]) => (
              <th key={code} scope="col" className="min-w-[110px] px-2 py-1.5 text-center font-medium text-muted-foreground">
                {name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {accounts.map(([code, name]) => (
            <tr key={code}>
              <th scope="row" className="px-2 py-1.5 text-left font-medium whitespace-nowrap text-foreground">
                {name}
              </th>
              {units.map(([unitCode]) => {
                const cell = cellOf.get(`${code}|${unitCode}`)
                if (!cell) return <td key={unitCode} className="rounded-[4px] bg-muted text-center text-subtle">·</td>
                // Colour follows the effect on profit, not the sign of the number.
                const direction = cell.status === 'on_target' ? 0 : cell.status === 'favorable' ? 1 : -1
                const intensity = Math.min(1, Math.abs(cell.variance_pct ?? 0) / FULL_INTENSITY)
                return (
                  <td
                    key={unitCode}
                    className={cn('tabular h-8 rounded-[4px] px-2 text-center', direction === 0 ? 'text-muted-foreground' : 'text-white')}
                    style={{ backgroundColor: divergingColor(direction * intensity) }}
                    title={`${cell.business_unit_name} · ${cell.account_name}: ${formatSignedCurrency(cell.variance)} (${cell.status.replace('_', ' ')})`}
                  >
                    {formatSignedPercent(cell.variance_pct)}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground" aria-hidden>
        Unfavorable
        <span className="flex h-2 w-48 overflow-hidden rounded-full">
          {[-1, -0.6, -0.3, 0, 0.3, 0.6, 1].map((step) => (
            <span key={step} className="flex-1" style={{ backgroundColor: divergingColor(step) }} />
          ))}
        </span>
        Favorable
        <span className="ml-2 text-subtle">Cells show variance % of budget. Variances under 1.5% stay neutral; full intensity at ±25%.</span>
      </div>
    </div>
  )
}

function MatrixPanel() {
  const matrix = useBudgetMatrix()
  return (
    <Panel
      title="Where the variances are"
      description="Variance % of budget for every account and business unit, coloured by its effect on profit"
      stale={isStale(matrix)}
    >
      <QueryBoundary query={matrix} minHeight={420} isEmpty={(data) => data.cells.length === 0}>
        {(data) => <VarianceMatrix data={data} />}
      </QueryBoundary>
    </Panel>
  )
}

export default function Budget() {
  return (
    <div className="space-y-4">
      <BudgetSummary />
      <div className="grid gap-4 xl:grid-cols-3">
        <MonthlyVariancePanel />
        <UnitVariancePanel />
      </div>
      <BudgetBridgePanel />
      <StatementPanel />
      <MatrixPanel />
    </div>
  )
}
