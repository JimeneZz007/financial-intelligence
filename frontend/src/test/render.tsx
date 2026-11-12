import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, useLocation } from 'react-router'

import { TooltipProvider } from '@/components/ui/tooltip'
import { FiltersProvider } from '@/lib/filters'

import { dimensions } from './fixtures'

/** Exposes the current URL so tests can assert on what the filters wrote to it. */
function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{`${location.pathname}${location.search}`}</output>
}

export function renderWithProviders(ui: ReactElement, { route = '/' }: { route?: string } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[route]}>
          <FiltersProvider dimensions={dimensions}>
            {ui}
            <LocationProbe />
          </FiltersProvider>
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  )
}

/** Replaces `fetch` with a handler keyed by API path; returns the list of requested URLs. */
export function mockApi(handlers: Record<string, (url: URL) => unknown>): URL[] {
  const calls: URL[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input), 'http://localhost')
      calls.push(url)
      const path = url.pathname.replace('/api/v1', '')
      const handler = handlers[path]
      if (!handler) {
        return new Response(JSON.stringify({ detail: `No mock for ${path}` }), { status: 404 })
      }
      return new Response(JSON.stringify(handler(url)), { status: 200, headers: { 'Content-Type': 'application/json' } })
    }),
  )
  return calls
}
