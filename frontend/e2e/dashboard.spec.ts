import { expect, test } from '@playwright/test'

import { closeMenu, kpiValue, openOverview, selectPeriod, selectUnit, tableRows, trackErrors } from './helpers.ts'

/**
 * The dataset is generated with a fixed seed, so headline figures are stable and can be
 * asserted literally. They match docs/API_REFERENCE.md and the Python integration tests.
 */
test.describe('Overview', () => {
  test('shows the headline KPIs of the default selection', async ({ page }) => {
    const errors = trackErrors(page)
    await openOverview(page)

    await expect(kpiValue(page, 'net_revenue')).toHaveText('$59.1M')
    await expect(kpiValue(page, 'direct_costs')).toHaveText('$40.8M')
    await expect(kpiValue(page, 'operating_income')).toHaveText('$4.0M')
    await expect(kpiValue(page, 'operating_margin')).toHaveText('6.8%')
    await expect(page.getByTestId('context-line')).toContainText('FY 2025')
    await expect(page.getByTestId('context-line')).toContainText('All business units')

    const revenue = page.getByRole('article', { name: 'Net revenue' })
    await expect(revenue.getByText('+13.4%')).toBeVisible() // vs prior year
    await expect(revenue.getByText('+0.6%')).toBeVisible() // vs budget
    expect(errors).toEqual([])
  })

  test('renders every block with data from the API', async ({ page }) => {
    await openOverview(page)
    for (const title of [
      'Financial evolution',
      'Budget vs actual',
      'Revenue by category',
      'Operating expenses by group',
      'Business units',
      'Key findings',
      'Monthly results',
    ]) {
      await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible()
    }
    // The chart is real vector output, not a placeholder.
    const chart = page.getByRole('img', { name: /Net revenue by month/ })
    await expect(chart.locator('svg')).toBeVisible()
    expect(await chart.locator('svg path').count()).toBeGreaterThan(12) // at least one mark per month
    await expect(page.getByRole('list', { name: 'Net revenue by product category' }).getByRole('listitem')).toHaveCount(5)
    await expect(page.getByRole('table', { name: 'Business unit comparison' }).locator('tbody tr')).toHaveCount(4)
    await expect(page.getByTestId('insight-operating_income')).toContainText('Operating income rose $542K')
  })

  test('switches the metric of the evolution chart', async ({ page }) => {
    await openOverview(page)
    await page.getByRole('radio', { name: 'Operating margin' }).click()
    await expect(page.getByRole('img', { name: /Operating margin by month/ })).toBeVisible()
    await expect(page.getByText('Monthly operating margin: actual against budget')).toBeVisible()
  })

  test('offers every chart as a data table', async ({ page }) => {
    await openOverview(page)
    await page.getByRole('button', { name: 'Show data table: Financial evolution' }).click()
    const section = page.getByRole('region', { name: 'Financial evolution' })
    await expect(section.locator('tbody tr')).toHaveCount(12)
    await expect(section.getByRole('cell', { name: 'Dec 2025' })).toBeVisible()
    await page.getByRole('button', { name: 'Show chart: Financial evolution' }).click()
    await expect(page.getByRole('img', { name: /Net revenue by month/ })).toBeVisible()
  })
})

test.describe('Global filters', () => {
  test('a business unit recalculates KPIs, charts, tables and findings', async ({ page }) => {
    await openOverview(page)
    await expect(page.getByTestId('insight-top_business_unit')).toBeVisible()

    await selectUnit(page, 'ECM')

    await expect(kpiValue(page, 'net_revenue')).toHaveText('$13.6M')
    await expect(kpiValue(page, 'operating_margin')).toHaveText('4.3%')
    await expect(page.getByTestId('context-line')).toContainText('E-commerce')
    await expect(page).toHaveURL(/bu=ECM/)

    // Tables: only the selected unit remains.
    await expect(page.getByRole('table', { name: 'Business unit comparison' }).locator('tbody tr')).toHaveCount(1)
    await expect(page.getByText('1–12 of 12 rows')).toBeVisible() // wait for the filtered page
    const records = await tableRows(page.getByRole('table', { name: 'Monthly results by business unit' }))
    expect(records.length).toBe(12)
    expect(new Set(records.map((row) => row[1]))).toEqual(new Set(['E-commerce']))

    // Findings: ranking units makes no sense with a single unit, so that finding goes away.
    await expect(page.getByTestId('insight-top_business_unit')).toHaveCount(0)
    await expect(page.getByTestId('insight-revenue_vs_budget')).toContainText('$13.6M actual')
  })

  test('several units add up and "all" clears the filter', async ({ page }) => {
    await openOverview(page)
    await page.getByTestId('unit-filter').click()
    await page.getByTestId('unit-option-RET').click()
    await page.getByTestId('unit-option-WHS').click()
    await closeMenu(page)

    await expect(page.getByTestId('unit-filter')).toContainText('2 business units')
    await expect(kpiValue(page, 'net_revenue')).toHaveText('$36.5M') // 20.5M + 16.0M
    await expect(page).toHaveURL(/bu=RET(%2C|,)WHS/)

    await page.getByTestId('unit-filter').click()
    await page.getByTestId('unit-option-all').click()
    await expect(kpiValue(page, 'net_revenue')).toHaveText('$59.1M')
    await expect(page).not.toHaveURL(/bu=/)
  })

  test('a period preset changes the data and the comparison', async ({ page }) => {
    await openOverview(page)
    await selectPeriod(page, 'FY 2024')

    await expect(kpiValue(page, 'net_revenue')).toHaveText('$52.1M')
    await expect(page.getByTestId('period-filter')).toContainText('FY 2024')
    await expect(page).toHaveURL(/from=2024-01&to=2024-12/)
    await expect(page.getByRole('region', { name: 'Financial evolution' })).toBeVisible()
  })

  test('the first year has no prior year: comparisons say so instead of showing a number', async ({ page }) => {
    await openOverview(page)
    await selectPeriod(page, 'FY 2023')

    await expect(kpiValue(page, 'net_revenue')).toHaveText('$49.3M')
    const revenue = page.getByRole('article', { name: 'Net revenue' })
    await expect(revenue.getByText('No data')).toBeVisible()
    await expect(revenue.getByText('vs budget')).toBeVisible()
    await expect(page.getByTestId('insight-operating_income')).toContainText('No prior year data')
  })

  test('the comparison basis changes the deltas', async ({ page }) => {
    await openOverview(page, '?from=2025-07&to=2025-09')
    const revenue = page.getByRole('article', { name: 'Net revenue' })
    await expect(revenue.getByText('vs prior year')).toBeVisible()
    const priorYear = await revenue.locator('dd').first().innerText()

    await page.getByTestId('compare-filter').click()
    await page.getByRole('option', { name: 'vs prior period' }).click()

    await expect(revenue.getByText('vs prior period')).toBeVisible()
    await expect(page).toHaveURL(/cmp=pp/)
    await expect(revenue.locator('dd').first()).not.toHaveText(priorYear)
  })

  test('a custom month range is applied', async ({ page }) => {
    await openOverview(page)
    await page.getByTestId('period-filter').click()
    await page.getByRole('combobox', { name: 'From month' }).click()
    await page.getByRole('option', { name: 'Apr 2024' }).click()
    await page.getByRole('combobox', { name: 'To month' }).click()
    await page.getByRole('option', { name: 'Jun 2024' }).click()
    await page.getByRole('button', { name: 'Apply range' }).click()

    await expect(page).toHaveURL(/from=2024-04&to=2024-06/)
    await expect(page.getByTestId('period-filter')).toContainText('Apr 2024 – Jun 2024')
    await expect(page.getByRole('table', { name: 'Monthly results by business unit' }).locator('tbody tr')).toHaveCount(12)
  })

  test('filters survive navigation and a reload', async ({ page }) => {
    await openOverview(page)
    await selectUnit(page, 'WHS')
    await selectPeriod(page, 'FY 2024')

    await page.getByRole('link', { name: 'Budget vs Actual' }).click()
    await expect(page).toHaveURL(/\/budget\?.*bu=WHS/)
    await expect(page.getByTestId('context-line')).toContainText('Wholesale Distribution')
    await expect(page.getByTestId('context-line')).toContainText('FY 2024')

    await page.reload()
    await expect(page.getByTestId('context-line')).toContainText('Wholesale Distribution')
    await expect(page.getByTestId('unit-filter')).toContainText('Wholesale Distribution')
  })

  test('an invalid selection in the URL falls back to the default', async ({ page }) => {
    await openOverview(page, '?from=1999-01&to=1999-12&bu=NOPE')
    await expect(kpiValue(page, 'net_revenue')).toHaveText('$59.1M')
    await expect(page.getByTestId('context-line')).toContainText('All business units')
  })
})

test.describe('Analytical table', () => {
  test('sorts on the server and paginates', async ({ page }) => {
    await openOverview(page)
    const table = page.getByRole('table', { name: 'Monthly results by business unit' })
    await expect(page.getByText('1–12 of 48 rows')).toBeVisible()

    await table.getByRole('button', { name: 'Net revenue' }).click()
    await expect(table.getByRole('columnheader', { name: 'Net revenue' })).toHaveAttribute('aria-sort', 'descending')
    // The previous page stays on screen while the sorted one loads: wait for the new first row.
    await expect(table.locator('tbody tr').first()).toContainText('$2,094,302') // Retail Stores, November 2025
    const amounts = (await tableRows(table)).map((row) => Number(row[2]!.replace(/[$,]/g, '')))
    expect(amounts).toEqual([...amounts].sort((a, b) => b - a))

    await page.getByRole('button', { name: 'Next page' }).click()
    await expect(page.getByText('13–24 of 48 rows')).toBeVisible()
    const nextAmounts = (await tableRows(table)).map((row) => Number(row[2]!.replace(/[$,]/g, '')))
    expect(Math.max(...nextAmounts)).toBeLessThanOrEqual(Math.min(...amounts))
  })

  test('filters rows by budget attainment', async ({ page }) => {
    await openOverview(page)
    await page.getByTestId('records-filter').click()
    await page.getByRole('option', { name: 'Revenue below budget' }).click()

    const table = page.getByRole('table', { name: 'Monthly results by business unit' })
    await expect(page.getByText('1–12 of 27 rows')).toBeVisible()
    const variances = (await tableRows(table)).map((row) => row.at(-1)!)
    expect(variances.length).toBeGreaterThan(0)
    for (const variance of variances) expect(variance).toMatch(/^-/)
  })

  test('exports the filtered data as CSV', async ({ page }) => {
    await openOverview(page)
    await selectUnit(page, 'COR')
    await expect(kpiValue(page, 'net_revenue')).toHaveText('$9.0M')

    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByTestId('export-monthly-pnl').click(),
    ])
    expect(download.suggestedFilename()).toBe('monthly-pnl_2025-01_2025-12_COR.csv')

    const stream = await download.createReadStream()
    const chunks: Buffer[] = []
    for await (const chunk of stream) chunks.push(chunk as Buffer)
    const lines = Buffer.concat(chunks).toString('utf-8').trim().split('\n')
    expect(lines[0]).toContain('month,business_unit_code,business_unit_name,net_revenue')
    expect(lines).toHaveLength(13) // header + 12 months of one unit
    expect(lines.slice(1).every((line) => line.includes(',COR,'))).toBe(true)
  })
})

test.describe('Resilience', () => {
  test('a failing endpoint shows an error in its panel and can be retried', async ({ page }) => {
    let fail = true
    await page.route('**/api/v1/insights*', async (route) => {
      if (fail) await route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"The database is unavailable."}' })
      else await route.continue()
    })
    await openOverview(page)

    const panel = page.getByRole('region', { name: 'Key findings' })
    await expect(panel.getByRole('alert')).toContainText('The database is unavailable.')
    // The rest of the dashboard is unaffected.
    await expect(kpiValue(page, 'net_revenue')).toHaveText('$59.1M')

    fail = false
    await panel.getByRole('button', { name: 'Try again' }).click()
    await expect(page.getByTestId('insight-operating_income')).toBeVisible()
  })

  test('an unreachable API shows a clear message instead of a blank page', async ({ page }) => {
    await page.route('**/api/v1/**', (route) => route.abort())
    await page.goto('/')
    await expect(page.getByRole('alert')).toContainText('The application could not load its data')
    await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible()
  })
})
