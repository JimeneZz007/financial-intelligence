import { useQuery } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CircleDollarSign } from 'lucide-react'
import { describe, expect, it } from 'vitest'

import { kpi } from '@/test/fixtures'
import { renderWithProviders } from '@/test/render'

import { DataTable, Pagination, type Column } from './DataTable'
import { Delta, StatusBadge } from './Delta'
import { InsightList } from './InsightList'
import { KpiTile } from './KpiTile'
import { ChartPanel } from './Panel'
import { QueryBoundary } from './QueryBoundary'
import { RankedBars } from './RankedBars'

describe('Delta', () => {
  it('separates the direction of the number from whether it is good news', () => {
    render(<Delta text="+15.5%" direction="up" status="unfavorable" />)
    const delta = screen.getByText('+15.5%')
    // Costs went up: the arrow says "up", the colour and the label say "unfavorable".
    expect(delta).toHaveClass('text-unfavorable-text')
    expect(within(delta).getByText('(Unfavorable)')).toHaveClass('sr-only')
  })

  it('never relies on colour alone for a status', () => {
    render(<StatusBadge status="favorable" />)
    expect(screen.getByText('Favorable')).toBeVisible()
  })
})

describe('KpiTile', () => {
  it('shows the value with its change against the comparison period and the budget', () => {
    render(<KpiTile kpi={kpi()} icon={CircleDollarSign} comparisonLabel="prior year" />)
    const tile = screen.getByRole('article', { name: 'Net revenue' })
    expect(within(tile).getByText('$59.1M')).toBeVisible()
    expect(within(tile).getByText('vs prior year')).toBeVisible()
    expect(within(tile).getByText('+13.4%')).toBeVisible()
    expect(within(tile).getByText('+0.6%')).toBeVisible()
  })

  it('reports margin changes in percentage points', () => {
    render(
      <KpiTile
        kpi={kpi({ id: 'operating_margin', label: 'Operating margin', unit: 'percent', value: 0.0676, change: 0.00137, change_pct: null, budget_variance: -0.0157, budget_variance_pct: null, budget_status: 'unfavorable' })}
        icon={CircleDollarSign}
        comparisonLabel="prior year"
      />,
    )
    expect(screen.getByText('6.8%')).toBeVisible()
    expect(screen.getByText('+0.1 pp')).toBeVisible()
    expect(screen.getByText('-1.6 pp')).toBeVisible()
  })

  it('says "No data" instead of inventing a comparison', () => {
    render(
      <KpiTile
        kpi={kpi({ comparison_value: null, change: null, change_pct: null, comparison_status: null })}
        icon={CircleDollarSign}
        comparisonLabel="prior year"
      />,
    )
    expect(screen.getByText('No data')).toBeVisible()
    expect(screen.queryByText('+13.4%')).not.toBeInTheDocument()
    expect(screen.getByText('+0.6%')).toBeVisible() // the budget does not depend on history
  })
})

interface Row {
  name: string
  revenue: number | null
}

const ROWS: Row[] = [
  { name: 'Furniture', revenue: 9 },
  { name: 'Electronics', revenue: 20 },
  { name: 'Unknown', revenue: null },
  { name: 'Accessories', revenue: 7 },
]

const COLUMNS: Column<Row>[] = [
  { key: 'name', header: 'Category', sortValue: (row) => row.name, render: (row) => row.name },
  { key: 'revenue', header: 'Revenue', align: 'right', sortValue: (row) => row.revenue, render: (row) => row.revenue ?? '—' },
]

const names = () => screen.getAllByRole('row').slice(1).map((row) => within(row).getAllByRole('cell')[0]!.textContent)

describe('DataTable', () => {
  it('sorts on header click, announces the order and keeps missing values last', async () => {
    const user = userEvent.setup()
    render(<DataTable label="Categories" columns={COLUMNS} rows={ROWS} rowKey={(row) => row.name} />)
    expect(names()).toEqual(['Furniture', 'Electronics', 'Unknown', 'Accessories'])

    await user.click(screen.getByRole('button', { name: 'Revenue' }))
    expect(names()).toEqual(['Electronics', 'Furniture', 'Accessories', 'Unknown'])
    expect(screen.getByRole('columnheader', { name: 'Revenue' })).toHaveAttribute('aria-sort', 'descending')

    await user.click(screen.getByRole('button', { name: 'Revenue' }))
    expect(names()).toEqual(['Accessories', 'Furniture', 'Electronics', 'Unknown'])
    expect(screen.getByRole('columnheader', { name: 'Revenue' })).toHaveAttribute('aria-sort', 'ascending')

    await user.click(screen.getByRole('button', { name: 'Category' }))
    expect(names()).toEqual(['Accessories', 'Electronics', 'Furniture', 'Unknown'])
  })

  it('is operable from the keyboard', async () => {
    const user = userEvent.setup()
    render(<DataTable label="Categories" columns={COLUMNS} rows={ROWS} rowKey={(row) => row.name} />)
    await user.tab()
    expect(screen.getByRole('button', { name: 'Category' })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(names()[0]).toBe('Accessories')
  })

  it('reports sort requests instead of sorting when the server owns the order', async () => {
    const user = userEvent.setup()
    const requests: unknown[] = []
    render(
      <DataTable
        label="Categories"
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.name}
        sort={{ key: 'name', direction: 'asc' }}
        onSortChange={(sort) => requests.push(sort)}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Revenue' }))
    expect(requests).toEqual([{ key: 'revenue', direction: 'desc' }])
    expect(names()).toEqual(['Furniture', 'Electronics', 'Unknown', 'Accessories']) // untouched
  })

  it('limits the visible rows after sorting and renders a totals footer', () => {
    render(
      <DataTable
        label="Categories"
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.name}
        initialSort={{ key: 'revenue', direction: 'desc' }}
        limit={2}
        footer={{ name: 'Total', revenue: 36 }}
      />,
    )
    expect(names()).toEqual(['Electronics', 'Furniture', 'Total'])
  })
})

describe('Pagination', () => {
  it('describes the window and disables the buttons at the ends', async () => {
    const user = userEvent.setup()
    const pages: number[] = []
    const { rerender } = render(
      <Pagination page={1} totalPages={4} totalItems={48} pageSize={12} onPageChange={(page) => pages.push(page)} />,
    )
    expect(screen.getByText('1–12 of 48 rows')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Next page' }))
    expect(pages).toEqual([2])

    rerender(<Pagination page={4} totalPages={4} totalItems={48} pageSize={12} onPageChange={() => {}} />)
    expect(screen.getByText('37–48 of 48 rows')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled()
  })
})

describe('RankedBars', () => {
  it('prints every value, so nothing depends on hovering', () => {
    render(
      <RankedBars
        label="Revenue by category"
        rows={[
          { key: 'ELE', label: 'Electronics', value: 20, valueText: '$20.2M', detail: '34.2%' },
          { key: 'ACC', label: 'Accessories', value: 7, valueText: '$7.0M', detail: '11.9%' },
        ]}
      />,
    )
    const items = within(screen.getByRole('list', { name: 'Revenue by category' })).getAllByRole('listitem')
    expect(items).toHaveLength(2)
    expect(within(items[0]!).getByText('$20.2M')).toBeVisible()
    expect(within(items[1]!).getByText('11.9%')).toBeVisible()
  })
})

describe('ChartPanel', () => {
  it('offers the data table as an alternative to the chart', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <ChartPanel
        title="Financial evolution"
        table={{ columns: ['Month', 'Actual'], rows: [['Jan 2025', '$4.4M']] }}
      >
        <div>chart goes here</div>
      </ChartPanel>,
    )
    expect(screen.getByText('chart goes here')).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Show data table: Financial evolution' }))
    expect(screen.queryByText('chart goes here')).not.toBeInTheDocument()
    expect(screen.getByRole('cell', { name: '$4.4M' })).toBeVisible()
    await user.click(screen.getByRole('button', { name: 'Show chart: Financial evolution' }))
    expect(screen.getByText('chart goes here')).toBeVisible()
  })
})

describe('InsightList', () => {
  it('shows the figures behind a finding on demand', async () => {
    const user = userEvent.setup()
    render(
      <InsightList
        insights={[
          {
            id: 'revenue_vs_budget',
            category: 'budget',
            tone: 'positive',
            title: 'Net revenue finished 0.6% above budget',
            detail: '$59.1M actual against $58.7M budgeted.',
            evidence: [
              { label: 'Actual', value: 59_053_741.75, unit: 'currency' },
              { label: 'Variance %', value: 0.006066, unit: 'percent' },
            ],
          },
        ]}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Net revenue finished 0.6% above budget' })).toBeVisible()
    expect(screen.getByText('Positive finding')).toBeInTheDocument()
    await user.click(screen.getByText('Evidence'))
    expect(screen.getByText('$59,053,742')).toBeVisible()
    expect(screen.getByText('0.61%')).toBeVisible()
  })
})

function Probe({ mode }: { mode: 'ok' | 'empty' | 'error' }) {
  const query = useQuery({
    queryKey: ['probe', mode],
    queryFn: async () => {
      if (mode === 'error') throw new Error('Period 2030-01..2030-12 is outside the available data')
      return mode === 'empty' ? [] : ['row']
    },
  })
  return (
    <QueryBoundary query={query} isEmpty={(data) => data.length === 0}>
      {(data) => <p>{data.length} row loaded</p>}
    </QueryBoundary>
  )
}

describe('QueryBoundary', () => {
  it('shows a loading state, then the content', async () => {
    renderWithProviders(<Probe mode="ok" />)
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument()
    expect(await screen.findByText('1 row loaded')).toBeVisible()
  })

  it('explains an empty result', async () => {
    renderWithProviders(<Probe mode="empty" />)
    expect(await screen.findByText('No data for this selection')).toBeVisible()
  })

  it('shows the error from the API and lets the user retry', async () => {
    renderWithProviders(<Probe mode="error" />)
    const alert = await screen.findByRole('alert')
    expect(within(alert).getByText('Period 2030-01..2030-12 is outside the available data')).toBeVisible()
    expect(within(alert).getByRole('button', { name: /try again/i })).toBeEnabled()
  })
})
