import { ArrowRight, History } from 'lucide-react'
import { useMemo, useState } from 'react'

import { EChart } from '@/components/charts/EChart'
import { stackedColumnsOption } from '@/components/charts/options'
import { ExportButton, Segmented } from '@/components/common/controls'
import { DataTable, type Column } from '@/components/common/DataTable'
import { Delta, directionOf } from '@/components/common/Delta'
import { ChartPanel, Legend, Panel } from '@/components/common/Panel'
import { isStale, QueryBoundary, StateMessage } from '@/components/common/QueryBoundary'
import { RankedBars } from '@/components/common/RankedBars'
import { StatStrip, type Stat } from '@/components/common/StatStrip'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { Favorability, ProfitabilityRow, PvmResponse } from '@/lib/api'
import { unitColor } from '@/lib/chart-theme'
import { comparisonLabel, useFilters } from '@/lib/filters'
import {
  formatCurrency,
  formatCurrencyFull,
  formatInteger,
  formatMonth,
  formatPercent,
  formatPoints,
  formatSignedCurrency,
  formatSignedPercent,
} from '@/lib/format'
import { useProfitability, usePvm, useUnitSeries } from '@/lib/queries'

const growthStatus = (change: number | null | undefined): Favorability | null =>
  change == null ? null : Math.abs(change) < 0.005 ? 'on_target' : change > 0 ? 'favorable' : 'unfavorable'

function GrowthDelta({ change }: { change: number | null | undefined }) {
  if (change == null) return <span className="text-subtle">—</span>
  return <Delta text={formatSignedPercent(change)} direction={directionOf(change)} status={growthStatus(change)} />
}

// --------------------------------------------------------------------------- //
// Headline figures of the sales fact
// --------------------------------------------------------------------------- //
function SalesSummary() {
  const totals = useProfitability('category')
  const { compare } = useFilters()
  const stats = useMemo<Stat[] | undefined>(() => {
    const total = totals.data?.total
    if (!total) return undefined
    return [
      {
        label: 'Net revenue',
        value: formatCurrency(total.net_revenue),
        detail:
          total.revenue_change_pct == null ? (
            `No ${comparisonLabel(compare)} data`
          ) : (
            <span className="flex items-center gap-1.5">
              <GrowthDelta change={total.revenue_change_pct} /> vs {comparisonLabel(compare)}
            </span>
          ),
      },
      { label: 'Gross sales', value: formatCurrency(total.gross_sales), detail: 'Before discounts' },
      {
        label: 'Discount rate',
        value: formatPercent(total.discount_rate),
        detail: `${formatCurrency(total.discounts)} in discounts`,
      },
      {
        label: 'Units sold',
        value: formatInteger(total.units),
        detail: total.units ? `${formatCurrencyFull(total.net_revenue / total.units)} net per unit` : undefined,
      },
    ]
  }, [totals.data, compare])
  return <StatStrip label="Sales summary" stats={stats} stale={isStale(totals)} />
}

// --------------------------------------------------------------------------- //
// Revenue by business unit over time
// --------------------------------------------------------------------------- //
function UnitRevenuePanel() {
  const series = useUnitSeries()
  const { dimensions } = useFilters()

  // Units keep the order and colour of the catalogue, whatever the current ranking is.
  const stacks = useMemo(() => {
    const order = dimensions.business_units.map((unit) => unit.code)
    return [...(series.data?.series ?? [])]
      .sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key))
      .map((unit) => ({
        key: unit.key,
        label: unit.label,
        color: unitColor(unit.key),
        values: unit.points.map((point) => point.net_revenue),
      }))
  }, [series.data, dimensions])
  const months = useMemo(() => series.data?.series[0]?.points.map((point) => point.month) ?? [], [series.data])
  const option = useMemo(() => stackedColumnsOption(months, stacks), [months, stacks])

  return (
    <ChartPanel
      title="Revenue by business unit"
      description="Monthly net revenue, stacked by unit"
      className="xl:col-span-2"
      stale={isStale(series)}
      legend={<Legend items={stacks.map((unit) => ({ label: unit.label, color: unit.color, mark: 'bar' as const }))} />}
      table={{
        columns: ['Month', ...stacks.map((unit) => unit.label), 'Total'],
        rows: months.map((month, index) => [
          formatMonth(month),
          ...stacks.map((unit) => formatCurrency(unit.values[index])),
          formatCurrency(stacks.reduce((sum, unit) => sum + (unit.values[index] ?? 0), 0)),
        ]),
      }}
    >
      <QueryBoundary query={series} minHeight={320} isEmpty={(data) => data.series.length === 0}>
        {() => <EChart option={option} height={320} ariaLabel="Monthly net revenue stacked by business unit" />}
      </QueryBoundary>
    </ChartPanel>
  )
}

function UnitMixPanel() {
  const units = useProfitability('business_unit')
  const { compare } = useFilters()
  return (
    <Panel title="Revenue mix" description={`Share of net revenue and growth vs ${comparisonLabel(compare)}`} stale={isStale(units)}>
      <QueryBoundary query={units} minHeight={320} isEmpty={(data) => data.rows.length === 0}>
        {(data) => (
          <RankedBars
            fill
            label="Net revenue by business unit"
            rows={data.rows.map((row) => ({
              key: row.key,
              label: row.label,
              value: row.net_revenue,
              valueText: formatCurrency(row.net_revenue),
              color: unitColor(row.key),
              detail: (
                <span className="flex items-center gap-2">
                  {formatPercent(row.revenue_share)}
                  {row.revenue_change_pct != null ? <GrowthDelta change={row.revenue_change_pct} /> : null}
                </span>
              ),
            }))}
          />
        )}
      </QueryBoundary>
    </Panel>
  )
}

// --------------------------------------------------------------------------- //
// Price - volume - mix
// --------------------------------------------------------------------------- //
type PvmRow = PvmResponse['rows'][number]

const EFFECTS: { key: 'volume_effect' | 'mix_effect' | 'price_effect'; label: string; hint: string }[] = [
  { key: 'volume_effect', label: 'Volume', hint: 'More or fewer units at the previous mix and prices' },
  { key: 'mix_effect', label: 'Mix', hint: 'Units shifting between cheaper and dearer products' },
  { key: 'price_effect', label: 'Price', hint: 'Change in net revenue per unit, discounts included' },
]

/**
 * The three effects on one zero baseline. Drawing them as steps between two revenue
 * totals would start the axis at zero and flatten them into slivers; drawing only the
 * effects keeps their sizes comparable.
 */
function EffectBars({ total }: { total: PvmRow }) {
  const scale = Math.max(1, ...EFFECTS.map((effect) => Math.abs(total[effect.key])))
  return (
    <ul className="space-y-4" aria-label="Volume, mix and price effects on net revenue">
      {EFFECTS.map((effect) => {
        const value = total[effect.key]
        const width = (Math.abs(value) / scale) * 50
        return (
          <li key={effect.key}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-[13px] font-medium text-foreground">{effect.label}</span>
              <span className="tabular text-[13px] font-semibold text-foreground">{formatSignedCurrency(value)}</span>
            </div>
            <div className="relative mt-2 h-2.5 rounded-full bg-track" aria-hidden>
              <span className="absolute inset-y-[-3px] left-1/2 w-px bg-foreground/50" />
              <span
                className="absolute inset-y-0 rounded-[4px]"
                style={{
                  width: `${width}%`,
                  left: value >= 0 ? '50%' : `${50 - width}%`,
                  backgroundColor: value >= 0 ? 'var(--favorable)' : 'var(--unfavorable)',
                }}
              />
            </div>
            <p className="mt-1.5 text-[11px] text-muted-foreground">{effect.hint}</p>
          </li>
        )
      })}
    </ul>
  )
}

function PvmPanel() {
  const [groupBy, setGroupBy] = useState<'category' | 'business_unit'>('category')
  const pvm = usePvm(groupBy)
  const { compare } = useFilters()

  const columns: Column<PvmRow>[] = [
    {
      key: 'label',
      header: groupBy === 'category' ? 'Category' : 'Business unit',
      sortValue: (row) => row.label,
      render: (row) => <span className="font-medium text-foreground">{row.label}</span>,
    },
    { key: 'base', header: 'Before', align: 'right', sortValue: (row) => row.base_revenue, render: (row) => formatCurrency(row.base_revenue) },
    { key: 'volume', header: 'Volume', align: 'right', sortValue: (row) => row.volume_effect, render: (row) => formatSignedCurrency(row.volume_effect) },
    { key: 'mix', header: 'Mix', align: 'right', sortValue: (row) => row.mix_effect, render: (row) => formatSignedCurrency(row.mix_effect) },
    { key: 'price', header: 'Price', align: 'right', sortValue: (row) => row.price_effect, render: (row) => formatSignedCurrency(row.price_effect) },
    {
      key: 'total',
      header: 'Change',
      align: 'right',
      sortValue: (row) => row.total_change,
      render: (row) => <span className="font-medium text-foreground">{formatSignedCurrency(row.total_change)}</span>,
    },
    { key: 'current', header: 'Now', align: 'right', sortValue: (row) => row.current_revenue, render: (row) => formatCurrency(row.current_revenue) },
  ]

  return (
    <Panel
      title="What moved revenue"
      description={`Change vs ${comparisonLabel(compare)}, split into volume, mix and price`}
      stale={isStale(pvm)}
      actions={
        <Segmented
          label="Detail by"
          value={groupBy}
          onChange={setGroupBy}
          options={[
            { value: 'category', label: 'By category' },
            { value: 'business_unit', label: 'By unit' },
          ]}
        />
      }
    >
      <QueryBoundary query={pvm} minHeight={280}>
        {(data) =>
          data.available && data.total ? (
            <div className="grid gap-x-10 gap-y-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
              <div>
                <p className="tabular flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-muted-foreground">
                  <span>
                    {data.filters.comparison_label}{' '}
                    <span className="font-semibold text-foreground">{formatCurrency(data.total.base_revenue)}</span>
                  </span>
                  <ArrowRight aria-hidden className="size-3.5 text-subtle" />
                  <span>
                    {data.filters.period_label}{' '}
                    <span className="font-semibold text-foreground">{formatCurrency(data.total.current_revenue)}</span>
                  </span>
                </p>
                <p className="mt-1 mb-5 text-2xl font-semibold tracking-tight text-foreground">
                  {formatSignedCurrency(data.total.total_change)}
                </p>
                <EffectBars total={data.total} />
              </div>
              <div className="min-w-0">
                <DataTable
                  label="Price, volume and mix effects by segment"
                  columns={columns}
                  rows={data.rows}
                  rowKey={(row) => row.key}
                  footer={data.total}
                  initialSort={{ key: 'total', direction: 'desc' }}
                  dense
                />
                <p className="mt-3 text-[11px] leading-relaxed text-subtle">
                  The three effects add up exactly to the change. The split between volume and mix adds units of
                  different products together, so read it as an approximation; the price effect and the total do not
                  depend on that convention.
                </p>
              </div>
            </div>
          ) : (
            <StateMessage
              icon={<History />}
              title="No comparison period available"
              hint="The price, volume and mix analysis needs a comparison period with data. Choose a later period or another comparison basis."
              minHeight={280}
            />
          )
        }
      </QueryBoundary>
    </Panel>
  )
}

// --------------------------------------------------------------------------- //
// Sales detail: categories or products
// --------------------------------------------------------------------------- //
const ALL_CATEGORIES = 'all'
type Level = 'category' | 'product'

function SalesDetailPanel() {
  const { dimensions, compare } = useFilters()
  const [level, setLevel] = useState<Level>('category')
  const [category, setCategory] = useState(ALL_CATEGORIES)
  const selectedCategory = level === 'product' && category !== ALL_CATEGORIES ? category : null
  const detail = useProfitability(level, selectedCategory)

  const columns = useMemo<Column<ProfitabilityRow>[]>(() => {
    const name: Column<ProfitabilityRow> = {
      key: 'label',
      header: level === 'category' ? 'Category' : 'Product',
      sortValue: (row) => row.label,
      render: (row) =>
        level === 'product' && row.key !== 'total' ? (
          <span className="flex flex-col">
            <span className="font-medium text-foreground">{row.label}</span>
            <span className="text-[11px] text-subtle">{row.key}</span>
          </span>
        ) : (
          <span className="font-medium text-foreground">{row.label}</span>
        ),
    }
    const parent: Column<ProfitabilityRow> = {
      key: 'category',
      header: 'Category',
      sortValue: (row) => row.parent_label,
      render: (row) => row.parent_label,
    }
    return [
      name,
      ...(level === 'product' ? [parent] : []),
      { key: 'units', header: 'Units', align: 'right', sortValue: (row) => row.units, render: (row) => formatInteger(row.units) },
      { key: 'net_revenue', header: 'Net revenue', align: 'right', sortValue: (row) => row.net_revenue, render: (row) => formatCurrencyFull(row.net_revenue) },
      { key: 'share', header: 'Share', align: 'right', sortValue: (row) => row.revenue_share, render: (row) => formatPercent(row.revenue_share) },
      { key: 'discount', header: 'Discount', align: 'right', title: 'Discounts as a share of gross sales', sortValue: (row) => row.discount_rate, render: (row) => formatPercent(row.discount_rate) },
      { key: 'margin', header: 'Gross margin', align: 'right', sortValue: (row) => row.gross_margin, render: (row) => formatPercent(row.gross_margin) },
      {
        key: 'margin_change',
        header: 'Margin change',
        align: 'right',
        title: 'Change in gross margin, in percentage points',
        sortValue: (row) => row.gross_margin_change,
        render: (row) =>
          row.gross_margin_change == null ? (
            '—'
          ) : (
            <Delta
              text={formatPoints(row.gross_margin_change)}
              direction={directionOf(row.gross_margin_change)}
              status={
                Math.abs(row.gross_margin_change) < 0.0005
                  ? 'on_target'
                  : row.gross_margin_change > 0
                    ? 'favorable'
                    : 'unfavorable'
              }
            />
          ),
      },
      {
        key: 'growth',
        header: `Revenue vs ${comparisonLabel(compare)}`,
        align: 'right',
        sortValue: (row) => row.revenue_change_pct,
        render: (row) => <GrowthDelta change={row.revenue_change_pct} />,
      },
    ]
  }, [level, compare])

  return (
    <Panel
      title="Sales detail"
      description={level === 'category' ? 'Revenue, discounting and margin by product category' : 'Every product in the selection'}
      stale={isStale(detail)}
      actions={
        <>
          <Segmented
            label="Level of detail"
            value={level}
            onChange={setLevel}
            options={[
              { value: 'category', label: 'Categories' },
              { value: 'product', label: 'Products' },
            ]}
          />
          {level === 'product' ? (
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger size="sm" className="h-7 text-xs" aria-label="Filter products by category" data-testid="category-filter">
                <SelectValue />
              </SelectTrigger>
              <SelectContent align="end">
                <SelectItem value={ALL_CATEGORIES} className="text-xs">All categories</SelectItem>
                {dimensions.categories.map((item) => (
                  <SelectItem key={item.code} value={item.code} className="text-xs">
                    {item.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : null}
          <ExportButton dataset="sales-by-product" />
        </>
      }
    >
      <QueryBoundary query={detail} minHeight={320} isEmpty={(data) => data.rows.length === 0}>
        {(data) => (
          <DataTable
            // Remount on a level change so the sort state starts fresh for the new columns.
            key={data.group_by}
            label={level === 'category' ? 'Sales by category' : 'Sales by product'}
            columns={columns}
            rows={data.rows}
            rowKey={(row) => row.key}
            footer={{
              ...data.total,
              label: data.group_by === 'product' ? `Total (${data.rows.length} products)` : 'Total',
              parent_label: '',
            }}
            initialSort={{ key: 'net_revenue', direction: 'desc' }}
            dense={data.group_by === 'product'}
          />
        )}
      </QueryBoundary>
    </Panel>
  )
}

export default function Revenue() {
  return (
    <div className="space-y-4">
      <SalesSummary />
      <div className="grid gap-4 xl:grid-cols-3">
        <UnitRevenuePanel />
        <UnitMixPanel />
      </div>
      <PvmPanel />
      <SalesDetailPanel />
    </div>
  )
}
