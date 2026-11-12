import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { FilterBar } from '@/components/layout/Filters'
import { kpiSummary } from '@/test/fixtures'
import { mockApi, renderWithProviders } from '@/test/render'

import Overview from './Overview'

// The chart library needs a real layout engine; charts are covered by the end-to-end tests.
vi.mock('@/components/charts/EChart', () => ({
  EChart: ({ ariaLabel }: { ariaLabel: string }) => <div role="img" aria-label={ariaLabel} />,
}))

const filters = kpiSummary([]).filters

function apiHandlers() {
  return {
    '/kpis/summary': (url: URL) => kpiSummary(url.searchParams.getAll('business_unit')),
    '/timeseries': () => ({ filters, points: [] }),
    '/budget/statement': () => ({ filters, lines: [] }),
    '/budget/variance': () => ({ filters, group_by: 'business_unit', rows: [] }),
    '/profitability': () => ({ filters, group_by: 'category', category: null, rows: [], total: {} }),
    '/expenses/breakdown': () => ({ filters, group_by: 'account_group', rows: [], total: {} }),
    '/insights': () => ({ filters, insights: [] }),
    '/records/monthly': () => ({
      filters,
      pagination: { page: 1, page_size: 12, total_items: 0, total_pages: 1 },
      sort_by: 'month',
      sort_dir: 'desc',
      revenue_vs_budget: 'all',
      rows: [],
    }),
  }
}

const lastCall = (calls: URL[], path: string) => calls.filter((url) => url.pathname.endsWith(path)).at(-1)!

describe('Overview', () => {
  it('renders the four headline KPIs from the API response', async () => {
    mockApi(apiHandlers())
    renderWithProviders(<Overview />)

    const revenue = await screen.findByRole('article', { name: 'Net revenue' })
    expect(within(revenue).getByText('$59.1M')).toBeVisible()
    expect(within(screen.getByRole('article', { name: 'Direct costs' })).getByText('$40.8M')).toBeVisible()
    expect(within(screen.getByRole('article', { name: 'Operating income' })).getByText('$4.0M')).toBeVisible()
    expect(within(screen.getByRole('article', { name: 'Operating margin' })).getByText('6.8%')).toBeVisible()
  })

  it('sends the default period and comparison to every analytic endpoint', async () => {
    const calls = mockApi(apiHandlers())
    renderWithProviders(<Overview />)
    await screen.findByRole('article', { name: 'Net revenue' })

    const analytic = calls.filter((url) => !url.pathname.endsWith('/health'))
    expect(analytic.length).toBeGreaterThanOrEqual(8)
    for (const url of analytic) {
      expect(url.searchParams.get('start')).toBe('2025-01')
      expect(url.searchParams.get('end')).toBe('2025-12')
      expect(url.searchParams.get('compare')).toBe('previous_year')
      expect(url.searchParams.getAll('business_unit')).toEqual([])
    }
  })

  it('reads the filters from the URL', async () => {
    const calls = mockApi(apiHandlers())
    renderWithProviders(<Overview />, { route: '/?from=2024-04&to=2024-06&bu=WHS&cmp=pp' })
    await screen.findByRole('article', { name: 'Net revenue' })

    const request = lastCall(calls, '/kpis/summary')
    expect(request.searchParams.get('start')).toBe('2024-04')
    expect(request.searchParams.get('end')).toBe('2024-06')
    expect(request.searchParams.getAll('business_unit')).toEqual(['WHS'])
    expect(request.searchParams.get('compare')).toBe('previous_period')
  })

  it('recalculates the KPIs when a business unit is selected', async () => {
    const user = userEvent.setup()
    const calls = mockApi(apiHandlers())
    renderWithProviders(
      <>
        <FilterBar />
        <Overview />
      </>,
    )
    const revenue = await screen.findByRole('article', { name: 'Net revenue' })
    expect(within(revenue).getByText('$59.1M')).toBeVisible()

    await user.click(screen.getByRole('button', { name: 'Business unit: All business units' }))
    await user.click(await screen.findByRole('menuitemcheckbox', { name: /E-commerce/ }))

    // The fixture returns 10M per selected unit, so the tile proves the new slice arrived.
    await waitFor(() => expect(within(revenue).getByText('$10.0M')).toBeVisible())
    expect(lastCall(calls, '/kpis/summary').searchParams.getAll('business_unit')).toEqual(['ECM'])
    expect(lastCall(calls, '/insights').searchParams.getAll('business_unit')).toEqual(['ECM'])
    expect(lastCall(calls, '/records/monthly').searchParams.getAll('business_unit')).toEqual(['ECM'])
    expect(screen.getByTestId('location')).toHaveTextContent('/?bu=ECM')
  })

  it('applies a period preset to the data and to the URL', async () => {
    const user = userEvent.setup()
    const calls = mockApi(apiHandlers())
    renderWithProviders(
      <>
        <FilterBar />
        <Overview />
      </>,
    )
    await screen.findByRole('article', { name: 'Net revenue' })

    await user.click(screen.getByRole('button', { name: 'Period: FY 2025' }))
    await user.click(await screen.findByRole('button', { name: /FY 2024/ }))

    await waitFor(() => expect(lastCall(calls, '/kpis/summary').searchParams.get('start')).toBe('2024-01'))
    expect(lastCall(calls, '/kpis/summary').searchParams.get('end')).toBe('2024-12')
    expect(screen.getByRole('button', { name: 'Period: FY 2024' })).toBeVisible()
    expect(screen.getByTestId('location')).toHaveTextContent('/?from=2024-01&to=2024-12')
  })

  it('shows empty states instead of blank panels when there is no data', async () => {
    mockApi(apiHandlers())
    renderWithProviders(<Overview />)
    expect(await screen.findByText('No findings for this selection')).toBeVisible()
    expect(screen.getByText('No months match this filter')).toBeVisible()
  })

  it('shows the API error in the affected panel only', async () => {
    const handlers = apiHandlers()
    // @ts-expect-error: removing a handler makes the mock answer 404 for that endpoint
    delete handlers['/insights']
    mockApi(handlers)
    renderWithProviders(<Overview />)

    const alert = await screen.findByRole('alert')
    expect(within(alert).getByText('No mock for /insights')).toBeVisible()
    expect(within(screen.getByRole('article', { name: 'Net revenue' })).getByText('$59.1M')).toBeVisible()
  })
})
