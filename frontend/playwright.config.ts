import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end tests run against the real stack: FastAPI on the PostgreSQL database loaded
 * by the pipeline, and the Vite dev server. Both are started here unless already running.
 *
 * Requires: `make db-init && make pipeline` (see docs/TESTING.md).
 */
const WEB_URL = 'http://127.0.0.1:5173'
const API_URL = 'http://127.0.0.1:8000'

export default defineConfig({
  testDir: './e2e',
  // The screenshot capture is a documentation task, run on demand with `npm run screenshots`.
  testIgnore: process.env.CAPTURE ? [] : ['**/capture.spec.ts'],
  fullyParallel: true,
  // The API is a single local process doing CPU-bound work per request: a few parallel
  // browsers are realistic, a dozen only measure contention.
  workers: 2,
  expect: { timeout: 10_000 },
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : [['list']],
  use: {
    baseURL: WEB_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
  webServer: [
    {
      command: '.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000',
      cwd: '..',
      url: `${API_URL}/api/v1/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort',
      url: WEB_URL,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
})
