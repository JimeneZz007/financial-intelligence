import { ChevronDown, ShieldCheck } from 'lucide-react'
import { useMemo, useState } from 'react'

import { EChart } from '@/components/charts/EChart'
import { linesOption } from '@/components/charts/options'
import { ExportButton, Segmented, ShowAllToggle } from '@/components/common/controls'
import { DataTable, type Column } from '@/components/common/DataTable'
import { StatusBadge } from '@/components/common/Delta'
import { InsightList } from '@/components/common/InsightList'
import { ChartPanel, Legend, Panel } from '@/components/common/Panel'
import { isStale, QueryBoundary, StateMessage } from '@/components/common/QueryBoundary'
import type { Anomaly, Insight } from '@/lib/api'
import { chartColors, unitColor } from '@/lib/chart-theme'
import {
  formatCurrency,
  formatMonth,
  formatSignedCurrency,
  formatSignedPercent,
} from '@/lib/format'
import { useAnomalies, useInsights, useTimeSeries } from '@/lib/queries'
import { cn } from '@/lib/utils'

const MOM_COLOR = '#3987e5'
const YOY_COLOR = '#c98500'

// --------------------------------------------------------------------------- //
// Growth
// --------------------------------------------------------------------------- //
function GrowthPanel() {
  const series = useTimeSeries()
  const { months, mom, yoy, option } = useMemo(() => {
    const points = series.data?.points ?? []
    const months = points.map((p) => p.month)
    const mom = points.map((p) => p.revenue_mom_pct)
    const yoy = points.map((p) => p.revenue_yoy_pct)
    const option = linesOption(
      months,
      [
        { label: 'vs previous month', color: MOM_COLOR, values: mom },
        { label: 'vs same month last year', color: YOY_COLOR, values: yoy },
      ],
      'percent',
      { zeroLine: true, signed: true },
    )
    return { months, mom, yoy, option }
  }, [series.data])
  const hasYoy = yoy.some((value) => value != null)
  return (
    <ChartPanel
      title="Revenue growth"
      description={
        hasYoy
          ? 'Month over month reflects the calendar; year over year removes seasonality'
          : 'Year-over-year growth needs data one year earlier, which this period does not have'
      }
      stale={isStale(series)}
      legend={
        <Legend
          items={[
            { label: 'vs previous month', color: MOM_COLOR, mark: 'line' },
            { label: 'vs same month last year', color: YOY_COLOR, mark: 'line' },
          ]}
        />
      }
      table={{
        columns: ['Month', 'vs previous month', 'vs same month last year'],
        rows: months.map((month, index) => [
          formatMonth(month),
          formatSignedPercent(mom[index]),
          formatSignedPercent(yoy[index]),
        ]),
      }}
    >
      <QueryBoundary query={series} minHeight={300} isEmpty={(data) => data.points.length === 0}>
        {() => <EChart option={option} height={300} ariaLabel="Net revenue growth by month, month over month and year over year" />}
      </QueryBoundary>
    </ChartPanel>
  )
}

function TrendPanel() {
  const series = useTimeSeries()
  const { months, revenue, rolling, option } = useMemo(() => {
    const points = series.data?.points ?? []
    const months = points.map((p) => p.month)
    const revenue = points.map((p) => p.net_revenue)
    const rolling = points.map((p) => p.revenue_rolling_3m)
    const option = linesOption(
      months,
      [
        { label: 'Net revenue', color: chartColors.series, values: revenue },
        { label: '3-month average', color: chartColors.budget, values: rolling },
      ],
      'currency',
      { area: true },
    )
    return { months, revenue, rolling, option }
  }, [series.data])
  return (
    <ChartPanel
      title="Revenue trend"
      description="Monthly net revenue and its trailing three-month average"
      stale={isStale(series)}
      legend={
        <Legend
          items={[
            { label: 'Net revenue', color: chartColors.series, mark: 'line' },
            { label: '3-month average', color: chartColors.budget, mark: 'line' },
          ]}
        />
      }
      table={{
        columns: ['Month', 'Net revenue', '3-month average'],
        rows: months.map((month, index) => [
          formatMonth(month),
          formatCurrency(revenue[index]),
          formatCurrency(rolling[index]),
        ]),
      }}
    >
      <QueryBoundary query={series} minHeight={300} isEmpty={(data) => data.points.length === 0}>
        {() => <EChart option={option} height={300} ariaLabel="Monthly net revenue and trailing three-month average" />}
      </QueryBoundary>
    </ChartPanel>
  )
}

// --------------------------------------------------------------------------- //
// Anomalies
// --------------------------------------------------------------------------- //
const ANOMALY_COLUMNS: Column<Anomaly>[] = [
  { key: 'month', header: 'Month', sortValue: (row) => row.month, render: (row) => formatMonth(row.month) },
  {
    key: 'unit',
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
    key: 'account',
    header: 'Account',
    sortValue: (row) => row.account_name,
    render: (row) => <span className="font-medium text-foreground">{row.account_name}</span>,
  },
  { key: 'actual', header: 'Actual', align: 'right', sortValue: (row) => row.actual, render: (row) => formatCurrency(row.actual) },
  { key: 'budget', header: 'Budget', align: 'right', sortValue: (row) => row.budget, render: (row) => formatCurrency(row.budget) },
  {
    key: 'variance',
    header: 'Variance',
    align: 'right',
    sortValue: (row) => Math.abs(row.variance),
    render: (row) => formatSignedCurrency(row.variance),
  },
  {
    key: 'variance_pct',
    header: 'Var. %',
    align: 'right',
    sortValue: (row) => row.variance_pct,
    render: (row) => formatSignedPercent(row.variance_pct),
  },
  {
    key: 'typical',
    header: 'Typical',
    align: 'right',
    title: 'Median variance % of this business unit and account over the whole history',
    sortValue: (row) => row.typical_variance_pct,
    render: (row) => formatSignedPercent(row.typical_variance_pct),
  },
  {
    key: 'z',
    header: 'Robust z',
    align: 'right',
    title: 'Modified z-score: distance from the typical variance in robust standard deviations',
    sortValue: (row) => Math.abs(row.robust_z),
    render: (row) => `${row.robust_z > 0 ? '+' : ''}${row.robust_z.toFixed(1)}`,
  },
  { key: 'status', header: 'Effect', sortValue: (row) => row.status, render: (row) => <StatusBadge status={row.status} /> },
  {
    key: 'material',
    header: 'Material',
    sortValue: (row) => (row.is_material ? 1 : 0),
    render: (row) => (row.is_material ? 'Yes' : <span className="text-subtle">No</span>),
  },
]

const ANOMALY_PREVIEW = 8

function AnomaliesPanel() {
  const [scope, setScope] = useState<'material' | 'all'>('material')
  const [expanded, setExpanded] = useState(false)
  const anomalies = useAnomalies(scope === 'all')
  return (
    <Panel
      title="Unusual months"
      description="Months whose budget variance is far from what is typical for that unit and account"
      stale={isStale(anomalies)}
      actions={
        <>
          <Segmented
            label="Anomalies to show"
            value={scope}
            onChange={setScope}
            options={[
              { value: 'material', label: 'Material' },
              { value: 'all', label: 'All' },
            ]}
          />
          <ExportButton dataset="anomalies" />
        </>
      }
    >
      <QueryBoundary query={anomalies} minHeight={280}>
        {(data) => {
          const unfavorable = data.anomalies.filter((item) => item.status === 'unfavorable').length
          return (
            <div className="space-y-4">
              {data.anomalies.length === 0 ? (
                <StateMessage
                  icon={<ShieldCheck />}
                  title={scope === 'material' ? 'No material anomalies in this period' : 'No anomalies in this period'}
                  hint="No business unit and account shows a variance that is unusual for its own history."
                  minHeight={180}
                />
              ) : (
                <>
                  <p className="text-xs text-muted-foreground" data-testid="anomaly-summary">
                    <span className="font-semibold text-foreground">{data.anomalies.length}</span>{' '}
                    {data.anomalies.length === 1 ? 'anomaly' : 'anomalies'}:{' '}
                    <span className="text-unfavorable-text">{unfavorable} unfavorable</span>,{' '}
                    <span className="text-favorable-text">{data.anomalies.length - unfavorable} favorable</span>. Scored
                    over {data.method.months_of_history} months of history across {data.method.series_evaluated} series.
                  </p>
                  <div>
                    <DataTable
                      label="Anomalies"
                      columns={ANOMALY_COLUMNS}
                      rows={data.anomalies}
                      rowKey={(row) => `${row.month}-${row.business_unit_code}-${row.account_code}`}
                      initialSort={{ key: 'z', direction: 'desc' }}
                      limit={expanded ? undefined : ANOMALY_PREVIEW}
                      dense
                    />
                    {data.anomalies.length > ANOMALY_PREVIEW ? (
                      <ShowAllToggle
                        expanded={expanded}
                        total={data.anomalies.length}
                        noun="anomalies"
                        onToggle={() => setExpanded((value) => !value)}
                      />
                    ) : null}
                  </div>
                </>
              )}
              <details className="group rounded-lg bg-muted/50 px-3.5 py-2.5 text-xs">
                <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 font-medium text-foreground [&::-webkit-details-marker]:hidden">
                  <ChevronDown aria-hidden className="size-3.5 transition-transform group-open:rotate-180" />
                  How anomalies are detected
                </summary>
                <dl className="mt-3 grid gap-x-4 gap-y-2 leading-relaxed text-muted-foreground sm:grid-cols-[7rem_1fr]">
                  <dt className="font-medium text-foreground/90">Signal</dt>
                  <dd>{data.method.signal}. The budget already carries the expected level, trend and seasonality.</dd>
                  <dt className="font-medium text-foreground/90">Score</dt>
                  <dd>{data.method.score}. The median and MAD are barely moved by the anomalies themselves.</dd>
                  <dt className="font-medium text-foreground/90">Threshold</dt>
                  <dd>|z| &gt; {data.method.z_threshold} and at least 1 percentage point away from the typical variance.</dd>
                  <dt className="font-medium text-foreground/90">Materiality</dt>
                  <dd>{data.method.materiality}.</dd>
                  <dt className="font-medium text-foreground/90">Limits</dt>
                  <dd>
                    It says a month is unusual, not why. With 36 observations, pure noise alone triggers a flag in
                    about 9% of series, and effects spread thinly over many months go undetected.
                  </dd>
                </dl>
              </details>
            </div>
          )
        }}
      </QueryBoundary>
    </Panel>
  )
}

// --------------------------------------------------------------------------- //
// Findings
// --------------------------------------------------------------------------- //
const CATEGORIES: { value: Insight['category'] | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'performance', label: 'Performance' },
  { value: 'budget', label: 'Budget' },
  { value: 'expenses', label: 'Expenses' },
  { value: 'profitability', label: 'Profitability' },
  { value: 'trend', label: 'Trend' },
  { value: 'anomaly', label: 'Anomaly' },
]

function FindingsPanel() {
  const insights = useInsights()
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]['value']>('all')
  const all = insights.data?.insights ?? []
  const visible = category === 'all' ? all : all.filter((item) => item.category === category)
  return (
    <Panel
      title="Findings"
      description="Statements computed from the current selection; each one shows the figures behind it"
      stale={isStale(insights)}
    >
      <QueryBoundary
        query={insights}
        minHeight={280}
        isEmpty={(data) => data.insights.length === 0}
        emptyTitle="No findings for this selection"
      >
        {() => (
          <div className="space-y-4">
            <div role="group" aria-label="Filter findings by category" className="flex flex-wrap gap-1.5">
              {CATEGORIES.filter((item) => item.value === 'all' || all.some((insight) => insight.category === item.value)).map(
                (item) => {
                  const count = item.value === 'all' ? all.length : all.filter((insight) => insight.category === item.value).length
                  const active = category === item.value
                  return (
                    <button
                      key={item.value}
                      type="button"
                      aria-pressed={active}
                      onClick={() => setCategory(item.value)}
                      className={cn(
                        'inline-flex h-7 items-center gap-1.5 rounded-full border px-3 text-xs font-medium transition-colors',
                        active
                          ? 'border-brand/50 bg-brand/10 text-foreground'
                          : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground',
                      )}
                    >
                      {item.label}
                      <span className="tabular text-[11px] text-subtle">{count}</span>
                    </button>
                  )
                },
              )}
            </div>
            <InsightList insights={visible} grid />
          </div>
        )}
      </QueryBoundary>
    </Panel>
  )
}

export default function Trends() {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-2">
        <TrendPanel />
        <GrowthPanel />
      </div>
      <AnomaliesPanel />
      <FindingsPanel />
    </div>
  )
}
