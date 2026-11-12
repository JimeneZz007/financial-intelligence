import { expect, type Locator, type Page } from '@playwright/test'

/** Collects console errors and uncaught exceptions so a test can assert there were none. */
export function trackErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })
  page.on('pageerror', (error) => errors.push(String(error)))
  return errors
}

export const kpiValue = (page: Page, id: string): Locator => page.getByTestId(`kpi-value-${id}`)

/** Waits until the dashboard shows data for the default selection (FY 2025, all units). */
export async function openOverview(page: Page, search = ''): Promise<void> {
  await page.goto(`/${search}`)
  await expect(kpiValue(page, 'net_revenue')).toBeVisible()
}

export async function selectUnit(page: Page, code: string): Promise<void> {
  await page.getByTestId('unit-filter').click()
  await page.getByTestId(`unit-option-${code}`).click()
  await closeMenu(page)
}

/** Closes an open menu and waits for it to go, so focus has settled before the next action. */
export async function closeMenu(page: Page): Promise<void> {
  await page.keyboard.press('Escape')
  await expect(page.getByRole('menu')).toBeHidden()
}

export async function selectPeriod(page: Page, label: string): Promise<void> {
  await page.getByTestId('period-filter').click()
  await page.getByRole('button', { name: new RegExp(`^${label}`) }).click()
}

/** Text of every body row of a table, as arrays of cell texts. */
export async function tableRows(table: Locator): Promise<string[][]> {
  return table.locator('tbody tr').evaluateAll((rows) =>
    rows.map((row) => [...row.querySelectorAll('td')].map((cell) => (cell.textContent ?? '').trim())),
  )
}
