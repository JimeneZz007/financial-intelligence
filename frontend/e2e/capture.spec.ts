import { expect, test, type Page } from '@playwright/test'

import { kpiValue } from './helpers.ts'

/**
 * Captures the screenshots used in the documentation from the running application.
 * Run with `npm run screenshots`; output goes to docs/screenshots/.
 */
const OUT = '../docs/screenshots'

async function ready(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle')
  await expect(page.getByRole('status', { name: 'Loading' })).toHaveCount(0)
  await page.waitForTimeout(700) // let chart entry animations finish
}

const FULL_PAGES = [
  { path: '/', file: 'overview' },
  { path: '/revenue', file: 'revenue' },
  { path: '/costs', file: 'costs' },
  { path: '/profitability', file: 'profitability' },
  { path: '/budget', file: 'budget' },
  { path: '/trends', file: 'trends' },
  { path: '/data-quality', file: 'data-quality' },
  { path: '/methodology', file: 'methodology' },
]

test.describe.configure({ mode: 'serial' })

for (const view of FULL_PAGES) {
  test(`capture ${view.file}`, async ({ page }) => {
    await page.goto(view.path)
    await ready(page)
    await page.screenshot({ path: `${OUT}/${view.file}.png`, fullPage: true })
  })
}

test('capture hero (first screen of the overview, high resolution)', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 })
  const page = await context.newPage()
  await page.goto('/')
  await ready(page)
  await page.screenshot({ path: `${OUT}/hero.png` })
  await context.close()
})

test('capture filtered view (E-commerce, FY 2024)', async ({ page }) => {
  await page.goto('/?from=2024-01&to=2024-12&bu=ECM')
  await ready(page)
  await expect(kpiValue(page, 'net_revenue')).toHaveText('$11.0M')
  await page.screenshot({ path: `${OUT}/overview-filtered.png` })
})

test('capture period filter', async ({ page }) => {
  await page.goto('/')
  await ready(page)
  await page.getByTestId('period-filter').click()
  await expect(page.getByRole('button', { name: /^All time/ })).toBeVisible()
  await page.waitForTimeout(300)
  await page.screenshot({ path: `${OUT}/filters.png`, clip: { x: 640, y: 0, width: 800, height: 520 } })
})

test('capture chart tooltip', async ({ page }) => {
  await page.goto('/')
  await ready(page)
  const chart = page.getByRole('img', { name: /Net revenue by month/ })
  const box = (await chart.boundingBox())!
  await page.mouse.move(box.x + box.width * 0.72, box.y + box.height * 0.45)
  await page.waitForTimeout(400)
  await page.screenshot({
    path: `${OUT}/chart-tooltip.png`,
    clip: { x: box.x - 24, y: box.y - 110, width: box.width + 48, height: box.height + 150 },
  })
})

test('capture phone layout', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 })
  const page = await context.newPage()
  await page.goto('/')
  await ready(page)
  await page.screenshot({ path: `${OUT}/mobile-overview.png` })
  await page.getByRole('button', { name: 'Open navigation' }).click()
  await expect(page.getByRole('navigation', { name: 'Primary' })).toBeVisible()
  await page.waitForTimeout(400)
  await page.screenshot({ path: `${OUT}/mobile-navigation.png` })
  await context.close()
})
