import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

import { openOverview, selectUnit, tableRows, trackErrors } from './helpers.ts'

const VIEWS = [
  { path: '/', title: 'Overview', landmark: 'Financial evolution' },
  { path: '/revenue', title: 'Revenue', landmark: 'What moved revenue' },
  { path: '/costs', title: 'Costs & Expenses', landmark: 'Expense accounts' },
  { path: '/profitability', title: 'Profitability', landmark: 'What changed operating income' },
  { path: '/budget', title: 'Budget vs Actual', landmark: 'Income statement: actual vs budget' },
  { path: '/trends', title: 'Trends & Insights', landmark: 'Unusual months' },
  { path: '/data-quality', title: 'Data Quality', landmark: 'Data-quality rules' },
  { path: '/methodology', title: 'Methodology', landmark: 'KPI catalog' },
]

test.describe('Every view', () => {
  for (const view of VIEWS) {
    test(`${view.title} loads without errors`, async ({ page }) => {
      const errors = trackErrors(page)
      await page.goto(view.path)
      await expect(page.getByRole('heading', { level: 1, name: view.title }).first()).toBeVisible()
      await expect(page.getByRole('heading', { name: view.landmark, exact: true })).toBeVisible()
      await page.waitForLoadState('networkidle')
      await expect(page.getByRole('status', { name: 'Loading' })).toHaveCount(0)
      await expect(page.getByRole('alert')).toHaveCount(0)
      expect(errors).toEqual([])
    })

    test(`${view.title} has no serious accessibility violations`, async ({ page }) => {
      await page.goto(view.path)
      await expect(page.getByRole('heading', { name: view.landmark, exact: true })).toBeVisible()
      await page.waitForLoadState('networkidle')
      const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze()
      const serious = results.violations
        .filter((violation) => violation.impact === 'serious' || violation.impact === 'critical')
        .map((violation) => `${violation.id}: ${violation.nodes.length} node(s), e.g. ${violation.nodes[0]?.html.slice(0, 140)}`)
      expect(serious).toEqual([])
    })
  }

  test('the sidebar navigates between views and marks the current one', async ({ page }) => {
    await openOverview(page)
    const nav = page.getByRole('navigation', { name: 'Primary' })
    for (const view of VIEWS) {
      await nav.getByRole('link', { name: view.title, exact: true }).click()
      await expect(page).toHaveURL(new RegExp(`${view.path === '/' ? '/(\\?.*)?$' : view.path}`))
      await expect(nav.getByRole('link', { name: view.title, exact: true })).toHaveAttribute('aria-current', 'page')
    }
  })
})

test.describe('Analysis views', () => {
  test('Revenue: price, volume and mix add up to the change', async ({ page }) => {
    await page.goto('/revenue')
    const table = page.getByRole('table', { name: 'Price, volume and mix effects by segment' })
    await expect(table).toBeVisible()
    const total = table.locator('tfoot tr td')
    await expect(total.nth(2)).toHaveText('+$5.0M') // volume
    await expect(total.nth(3)).toHaveText('-$500K') // mix
    await expect(total.nth(4)).toHaveText('+$2.4M') // price
    await expect(total.nth(5)).toHaveText('+$7.0M') // change
  })

  test('Revenue: the category filter narrows the product table', async ({ page }) => {
    await page.goto('/revenue')
    await page.getByRole('radio', { name: 'Products' }).click()
    const table = page.getByRole('table', { name: 'Sales by product' })
    await expect(table.locator('tbody tr')).toHaveCount(30)

    await page.getByTestId('category-filter').click()
    await page.getByRole('option', { name: 'Furniture' }).click()
    await expect(table.locator('tbody tr')).toHaveCount(6)
    const categories = (await tableRows(table)).map((row) => row[1])
    expect(new Set(categories)).toEqual(new Set(['Furniture']))
  })

  test('Budget: the statement reconciles and the wholesale shortfall is visible', async ({ page }) => {
    await page.goto('/budget?from=2024-04&to=2024-06&bu=WHS')
    const statement = page.getByRole('table', { name: 'Income statement, actual against budget' })
    const revenue = statement.getByRole('row', { name: /Net Sales Revenue/ })
    await expect(revenue).toContainText('Unfavorable')
    await expect(revenue).toContainText('-26.1%')
    // Costs that fall with volume are favorable even though the unit sold less.
    await expect(statement.getByRole('row', { name: /Cost of Goods Sold/ })).toContainText('Favorable')
    await expect(statement.locator('tbody tr')).toHaveCount(16) // 13 accounts + 3 subtotals
  })

  test('Trends: anomalies respond to the materiality switch and the filters', async ({ page }) => {
    await page.goto('/trends?from=2023-01&to=2025-12')
    const summary = page.getByTestId('anomaly-summary')
    await expect(summary).toContainText('50 anomalies')
    await page.getByRole('radio', { name: 'All', exact: true }).click()
    await expect(summary).toContainText('80 anomalies')

    await page.getByRole('radio', { name: 'Material' }).click()
    await selectUnit(page, 'RET')
    await expect(summary).not.toContainText('50 anomalies')
    const rows = await tableRows(page.getByRole('table', { name: 'Anomalies' }))
    expect(new Set(rows.map((row) => row[1]))).toEqual(new Set(['Retail Stores']))
  })

  test('Trends: findings can be filtered by category', async ({ page }) => {
    await page.goto('/trends')
    const findings = page.getByRole('region', { name: 'Findings' })
    await expect(findings.getByRole('listitem')).toHaveCount(12)
    await findings.getByRole('button', { name: /^Budget/ }).click()
    await expect(findings.getByRole('listitem')).toHaveCount(2)
    await expect(findings.getByRole('button', { name: /^Budget/ })).toHaveAttribute('aria-pressed', 'true')
  })

  test('Data Quality: reports the latest run and its rules', async ({ page }) => {
    await page.goto('/data-quality')
    await expect(page.getByText('Succeeded').first()).toBeVisible()
    await expect(page.getByText('44 of 54')).toBeVisible()
    const loads = await tableRows(page.getByRole('table', { name: 'Rows per source extract' }))
    expect(loads.find((row) => row[0]!.includes('sales_transactions.csv'))?.slice(1, 6)).toEqual([
      '109,825',
      '25',
      '26',
      '40',
      '109,759',
    ])
    await page.getByRole('radio', { name: 'Handled' }).click()
    await expect(page.getByRole('table', { name: 'Data-quality rules' }).locator('tbody tr')).toHaveCount(10)
  })

  test('Methodology: KPI definitions come from the API and expand', async ({ page }) => {
    await page.goto('/methodology')
    await expect(page.getByText('Everything here is synthetic')).toBeVisible()
    const entry = page.getByTestId('kpi-definition-gross_margin')
    await entry.locator('summary').click()
    await expect(entry.getByText('Null when net revenue is 0.')).toBeVisible()
    await expect(page.locator('[data-testid^="kpi-definition-"]')).toHaveCount(16)
  })
})

test.describe('Keyboard and small screens', () => {
  test('the page is operable with the keyboard', async ({ page }) => {
    await openOverview(page)
    await page.keyboard.press('Tab')
    const skip = page.getByRole('link', { name: 'Skip to content' })
    await expect(skip).toBeFocused()
    await page.keyboard.press('Enter')
    await expect(page.locator('#main')).toBeFocused()

    // Open the period filter and choose a preset without the mouse.
    await page.getByTestId('period-filter').focus()
    await page.keyboard.press('Enter')
    const preset = page.getByRole('button', { name: /^FY 2024/ })
    await expect(preset).toBeVisible()
    await preset.focus()
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/from=2024-01&to=2024-12/)
  })

  test('on a phone the navigation is a drawer and nothing overflows sideways', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await openOverview(page)
    await expect(page.getByRole('navigation', { name: 'Primary' })).toHaveCount(0)

    for (const path of ['/', '/revenue', '/costs', '/profitability', '/budget', '/trends', '/data-quality', '/methodology']) {
      await page.goto(path)
      await page.waitForLoadState('networkidle')
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
      expect(overflow, `horizontal overflow on ${path}`).toBeLessThanOrEqual(0)
    }

    await page.goto('/')
    await page.getByRole('button', { name: 'Open navigation' }).click()
    await page.getByRole('navigation', { name: 'Primary' }).getByRole('link', { name: 'Profitability' }).click()
    await expect(page).toHaveURL(/\/profitability/)
    await expect(page.getByRole('heading', { level: 1, name: 'Profitability' })).toBeVisible()
  })
})
