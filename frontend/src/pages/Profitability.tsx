import { History } from 'lucide-react'
import { useMemo } from 'react'

import { EChart } from '@/components/charts/EChart'
import { miniLineOption, waterfallOption } from '@/components/charts/options'
import { DataTable, type Column } from '@/components/common/DataTable'
import { Delta, directionOf } from '@/components/common/Delta'
import { ChartPanel, Legend, Panel } from '@/components/common/Panel'
import { isStale, QueryBoundary, StateMessage } from '@/components/common/QueryBoundary'
import { StatStrip, type Stat } from '@/components/common/StatStrip'
import type { Favorability, Kpi, MarginDriversResponse, ProfitabilityRow } from '@/lib/api'
import { chartColors, unitColor } from '@/lib/chart-theme'
import { comparisonLabel, useFilters } from '@/lib/filters'
import { formatByUnit, formatChange, formatCurrency, formatPercent, formatPoints, formatSignedCurrency } from '@/lib/format'
import { useBridge, useKpis, useMarginDrivers, useProfitability, useUnitSeries } from '@/lib/queries'

const GROSS_COLOR = '#3987e5'
const OPERATING_COLOR = '#86b6ef'

const pointsStatus = (change: number | null | undefined): Favorability | null =>
  change == null ? null : Math.abs(change) < 0.0005 ? 'on_target' : change > 0 ? 'favorable' : 'unfavorable'

function PointsDelta({ change }: { change: number | null | undefined }) {
  if (change == null) return <span className="text-subtle">—</span>
  return <Delta text={formatPoints(change)} direction={directionOf(change)} status={pointsStatus(change)} />
}

// --------------------------------------------------------------------------- //
// Summary
// --------------------------------------------------------------------------- //
function ProfitSummary() {
  const kpis = useKpis()
  const { compare } = useFilters()
  const stats = useMemo<Stat[] | undefined>(() => {
    if (!kpis.data) return undefined
    const stat = (kpi: Kpi | undefined): Stat | null =>
      kpi
        ? {
            label: kpi.label,
            value: formatByUnit(kpi.value, kpi.unit),
            detail:
              kpi.change == null ? (
                `No ${comparisonLabel(compare)} data`
              ) : (
                <span className="flex items-center gap-1.5">
                  <Delta
                    text={formatChange(kpi.change, kpi.change_pct, kpi.unit)}
                    direction={directionOf(kpi.change)}
                    status={kpi.comparison_status}
                  />
                  vs {comparisonLabel(compare)}
                </span>
              ),
          }
        : null
    return ['gross_margin', 'operating_margin', 'gross_profit', 'operating_income']
      .map((id) => stat(kpis.data.kpis.find((kpi) => kpi.id === id)))
      .filter((item): item is Stat => item !== null)
  }, [kpis.data, compare])
  return <StatStrip label="Profitability summary" stats={stats} stale={isStale(kpis)} />
}

// --------------------------------------------------------------------------- //
// Operating income bridge
// --------------------------------------------------------------------------- //
function BridgePanel() {
  const bridge = useBridge('comparison')
  const { compare } = useFilters()
  const option = useMemo(() => waterfallOption(bridge.data?.steps ?? []), [bridge.data])
  return (
    <ChartPanel
      title="What changed operating income"
      description={`From ${comparisonLabel(compare)} to the selected period, line by line`}
      stale={isStale(bridge)}
      legend={
        <Legend
          items={[
            { label: 'Operating income', color: chartColors.series },
            { label: 'Improves profit', color: chartColors.favorable },
            { label: 'Reduces profit', color: chartColors.unfavorable },
          ]}
        />
      }
      table={
        bridge.data?.available
          ? {
              columns: ['Step', 'Amount'],
              rows: bridge.data.steps.map((step) => [
                step.label,
                step.kind === 'total' ? formatCurrency(step.amount) : formatSignedCurrency(step.amount),
              ]),
            }
          : undefined
      }
    >
      <QueryBoundary query={bridge} minHeight={320}>
        {(data) =>
          data.available ? (
            <EChart option={option} height={320} ariaLabel="Bridge of operating income between the comparison period and the selected period" />
          ) : (
            <StateMessage
              icon={<History />}
              title="No comparison period available"
              hint="The bridge needs a comparison period with data. Choose a later period or another comparison basis."
              minHeight={320}
            />
          )
        }
      </QueryBoundary>
    </ChartPanel>
  )
}

// --------------------------------------------------------------------------- //
// Margins by business unit
// --------------------------------------------------------------------------- //
function MarginBar({ label, value, scale, color }: { label: string; value: number | null | undefined; scale: number; color: string }) {
  return (
    <div className="grid grid-cols-[4.5rem_1fr_3.25rem] items-center gap-2 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="h-2 rounded-r-[4px] bg-track">
        <span
          className="block h-full rounded-r-[4px]"
          style={{ width: `${Math.max(0, ((value ?? 0) / scale) * 100)}%`, backgroundColor: color }}
        />
      </span>
      <span className="tabular text-right font-medium text-foreground">{formatPercent(value)}</span>
    </div>
  )
}

function UnitMarginsPanel() {
  const units = useProfitability('business_unit')
  return (
    <Panel
      title="Margins by business unit"
      description="Gross margin and operating margin"
      stale={isStale(units)}
      actions={
        <Legend
          items={[
            { label: 'Gross', color: GROSS_COLOR },
            { label: 'Operating', color: OPERATING_COLOR },
          ]}
        />
      }
    >
      <QueryBoundary query={units} minHeight={300} isEmpty={(data) => data.rows.length === 0}>
        {(data) => {
          const scale = Math.max(0.01, ...data.rows.map((row) => row.gross_margin ?? 0)) * 1.05
          return (
            <ul className="flex h-full flex-col justify-between gap-4" aria-label="Margins by business unit">
              {data.rows.map((row) => (
                <li key={row.key}>
                  <p className="mb-1.5 flex items-center gap-2 text-[13px] font-medium text-foreground">
                    <span aria-hidden className="size-2 rounded-[2px]" style={{ backgroundColor: unitColor(row.key) }} />
                    {row.label}
                  </p>
                  <div className="space-y-1.5">
                    <MarginBar label="Gross" value={row.gross_margin} scale={scale} color={GROSS_COLOR} />
                    <MarginBar label="Operating" value={row.operating_margin} scale={scale} color={OPERATING_COLOR} />
                  </div>
                </li>
              ))}
            </ul>
          )
        }}
      </QueryBoundary>
    </Panel>
  )
}

// --------------------------------------------------------------------------- //
// Operating margin over time: small multiples on a shared scale
// --------------------------------------------------------------------------- //
function MarginTrendPanel() {
  const series = useUnitSeries()
  const { dimensions } = useFilters()
  const panels = useMemo(() => {
    const units = series.data?.series ?? []
    const order = dimensions.business_units.map((unit) => unit.code)
    const values = units.flatMap((unit) => unit.points.map((p) => p.operating_margin).filter((v): v is number => v != null))
    // One scale for every panel, so heights are comparable across units.
    const range = {
      min: Math.floor(Math.min(0, ...values) * 10) / 10,
      max: Math.ceil(Math.max(0.1, ...values) * 10) / 10,
    }
    return [...units]
      .sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key))
      .map((unit) => {
        const months = unit.points.map((p) => p.month)
        const margins = unit.points.map((p) => p.operating_margin)
        return {
          key: unit.key,
          label: unit.label,
          // One hue for every panel: the caption names the unit, so colour carries no identity
          // here (four unit hues side by side would not be distinguishable for everyone).
          option: miniLineOption(months, margins, chartColors.series, range, 'Operating margin'),
        }
      })
  }, [series.data, dimensions])

  return (
    <Panel
      title="Operating margin over time"
      description="One panel per business unit, all on the same scale"
      className="xl:col-span-2"
      stale={isStale(series)}
    >
      <QueryBoundary query={series} minHeight={300} isEmpty={(data) => data.series.length === 0}>
        {() => (
          <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
            {panels.map((panel) => (
              <figure key={panel.key}>
                <figcaption className="mb-1 text-xs font-medium text-foreground">{panel.label}</figcaption>
                <EChart option={panel.option} height={128} ariaLabel={`Operating margin by month for ${panel.label}`} />
              </figure>
            ))}
          </div>
        )}
      </QueryBoundary>
    </Panel>
  )
}

// --------------------------------------------------------------------------- //
// Gross margin drivers: mix versus rate
// --------------------------------------------------------------------------- //
type DriverRow = MarginDriversResponse['rows'][number]

function EffectBar({ value, scale }: { value: number; scale: number }) {
  const width = Math.min(50, (Math.abs(value) / scale) * 50)
  return (
    <span className="relative hidden h-2 w-20 rounded-full bg-track align-middle sm:inline-block" aria-hidden>
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

function DriversPanel() {
  const drivers = useMarginDrivers('category')
  const { compare } = useFilters()
  const scale = Math.max(0.0005, ...(drivers.data?.rows ?? []).map((row) => Math.abs(row.total_effect)))
  const columns: Column<DriverRow>[] = [
    { key: 'label', header: 'Category', sortValue: (row) => row.label, render: (row) => <span className="font-medium text-foreground">{row.label}</span> },
    { key: 'margin', header: 'Margin', align: 'right', sortValue: (row) => row.current_margin, render: (row) => formatPercent(row.current_margin) },
    { key: 'rate', header: 'Rate', align: 'right', title: 'Effect of the change in the category margin', sortValue: (row) => row.rate_effect, render: (row) => formatPoints(row.rate_effect, 2) },
    { key: 'mix', header: 'Mix', align: 'right', title: 'Effect of the change in the category share of revenue', sortValue: (row) => row.mix_effect, render: (row) => formatPoints(row.mix_effect, 2) },
    {
      key: 'total',
      header: 'Contribution',
      align: 'right',
      sortValue: (row) => row.total_effect,
      render: (row) => (
        <span className="inline-flex items-center justify-end gap-2.5">
          <EffectBar value={row.total_effect} scale={scale} />
          <span className="w-16 font-medium text-foreground">{formatPoints(row.total_effect, 2)}</span>
        </span>
      ),
    },
  ]
  return (
    <Panel
      title="Gross margin drivers"
      description={`Contribution of each category to the change vs ${comparisonLabel(compare)}`}
      stale={isStale(drivers)}
    >
      <QueryBoundary query={drivers} minHeight={320}>
        {(data) =>
          data.available ? (
            <div className="space-y-4">
              <dl className="grid grid-cols-3 gap-3 text-xs">
                {[
                  { label: 'Margin change', value: data.margin_change },
                  { label: 'Rate effect', value: data.rate_effect },
                  { label: 'Mix effect', value: data.mix_effect },
                ].map((item) => (
                  <div key={item.label} className="rounded-lg bg-muted/60 px-3 py-2.5">
                    <dt className="text-muted-foreground">{item.label}</dt>
                    <dd className="mt-1 text-sm">
                      <PointsDelta change={item.value} />
                    </dd>
                  </div>
                ))}
              </dl>
              <DataTable
                label="Gross margin drivers by category"
                columns={columns}
                rows={data.rows}
                rowKey={(row) => row.key}
                initialSort={{ key: 'total', direction: 'asc' }}
                dense
              />
              <p className="text-[11px] leading-relaxed text-subtle">
                Rate: the category itself became more or less profitable. Mix: revenue shifted towards or away from
                it. Contributions add up exactly to the margin change.
              </p>
            </div>
          ) : (
            <StateMessage
              icon={<History />}
              title="No comparison period available"
              hint="Margin drivers need a comparison period with data."
              minHeight={320}
            />
          )
        }
      </QueryBoundary>
    </Panel>
  )
}

// --------------------------------------------------------------------------- //
// Category margins
// --------------------------------------------------------------------------- //
function CategoryMarginsPanel() {
  const categories = useProfitability('category')
  const columns: Column<ProfitabilityRow>[] = [
    { key: 'label', header: 'Category', sortValue: (row) => row.label, render: (row) => <span className="font-medium text-foreground">{row.label}</span> },
    { key: 'net_revenue', header: 'Net revenue', align: 'right', sortValue: (row) => row.net_revenue, render: (row) => formatCurrency(row.net_revenue) },
    { key: 'gross_profit', header: 'Gross profit', align: 'right', sortValue: (row) => row.gross_profit, render: (row) => formatCurrency(row.gross_profit) },
    {
      key: 'margin',
      header: 'Gross margin',
      align: 'right',
      sortValue: (row) => row.gross_margin,
      render: (row) => (
        <span className="inline-flex items-center justify-end gap-2.5">
          <span aria-hidden className="hidden h-1.5 w-16 overflow-hidden rounded-r-[3px] bg-track sm:block">
            <span className="block h-full rounded-r-[3px] bg-series" style={{ width: `${Math.max(0, (row.gross_margin ?? 0) * 100 * 1.6)}%` }} />
          </span>
          <span className="w-12">{formatPercent(row.gross_margin)}</span>
        </span>
      ),
    },
    {
      key: 'margin_change',
      header: 'Change',
      align: 'right',
      title: 'Change in gross margin, in percentage points',
      sortValue: (row) => row.gross_margin_change,
      render: (row) => <PointsDelta change={row.gross_margin_change} />,
    },
  ]
  return (
    <Panel
      title="Margin by category"
      description="Gross profit and margin; operating expenses are not recorded by product"
      stale={isStale(categories)}
    >
      <QueryBoundary query={categories} minHeight={320} isEmpty={(data) => data.rows.length === 0}>
        {(data) => (
          <DataTable
            label="Gross margin by category"
            columns={columns}
            rows={data.rows}
            rowKey={(row) => row.key}
            footer={data.total}
            initialSort={{ key: 'margin', direction: 'desc' }}
          />
        )}
      </QueryBoundary>
    </Panel>
  )
}

export default function Profitability() {
  return (
    <div className="space-y-4">
      <ProfitSummary />
      <BridgePanel />
      <div className="grid gap-4 xl:grid-cols-3">
        <UnitMarginsPanel />
        <MarginTrendPanel />
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <CategoryMarginsPanel />
        <DriversPanel />
      </div>
    </div>
  )
}
