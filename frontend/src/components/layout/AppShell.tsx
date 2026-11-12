import { CircleAlert, Menu, RotateCw } from 'lucide-react'
import { useState } from 'react'
import { Outlet, useLocation } from 'react-router'

import { StateMessage } from '@/components/common/QueryBoundary'
import { FilterBar } from '@/components/layout/Filters'
import { findNavItem } from '@/components/layout/navigation'
import { Brand, SidebarNav } from '@/components/layout/Sidebar'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { FiltersProvider, useFilters } from '@/lib/filters'
import { formatDateTime, formatMonth } from '@/lib/format'
import { useDimensions, useHealth } from '@/lib/queries'
import { cn } from '@/lib/utils'

/** Freshness of the data behind every figure, always visible in the top bar. */
function DataStatus() {
  const health = useHealth()
  const state = health.isError ? 'down' : health.data ? (health.data.data.loaded ? 'ok' : 'empty') : 'loading'
  const label = { ok: 'Data current', empty: 'No data loaded', down: 'API unreachable', loading: 'Checking…' }[state]
  const dot = { ok: 'bg-favorable', empty: 'bg-caution', down: 'bg-unfavorable', loading: 'bg-subtle' }[state]
  const data = health.data?.data

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" className="h-9 gap-2 px-2.5 text-[13px] font-medium text-muted-foreground" data-testid="data-status">
          <span className="relative flex size-2">
            {state === 'ok' ? <span className={cn('absolute inline-flex size-full animate-ping rounded-full opacity-40', dot)} /> : null}
            <span className={cn('relative inline-flex size-2 rounded-full', dot)} />
          </span>
          <span className="hidden sm:inline">{label}</span>
          <span className="sr-only sm:hidden">{label}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 text-xs">
        <p className="text-sm font-semibold text-foreground">{label}</p>
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
          <dt className="text-muted-foreground">Last load</dt>
          <dd className="text-right text-foreground">{formatDateTime(data?.last_successful_run_at)}</dd>
          <dt className="text-muted-foreground">Coverage</dt>
          <dd className="text-right text-foreground">
            {data?.period_start && data.period_end
              ? `${formatMonth(data.period_start)} – ${formatMonth(data.period_end)}`
              : '—'}
          </dd>
          <dt className="text-muted-foreground">Database</dt>
          <dd className="text-right text-foreground">{health.data?.database ?? (health.isError ? 'unknown' : '—')}</dd>
          <dt className="text-muted-foreground">Source</dt>
          <dd className="text-right text-foreground">Synthetic dataset</dd>
        </dl>
        <p className="mt-3 border-t pt-3 leading-relaxed text-muted-foreground">
          All figures are generated for a fictional company. They do not describe any real business.
        </p>
      </PopoverContent>
    </Popover>
  )
}

function TopBar() {
  const { pathname } = useLocation()
  const page = findNavItem(pathname)
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <header className="sticky top-0 z-30 border-b bg-background/85 backdrop-blur-md">
      {/* One row on wide screens; below that the filters wrap onto their own row. */}
      <div className="flex flex-wrap items-center gap-x-3 xl:h-16 xl:flex-nowrap xl:px-6">
        <div className="flex h-16 min-w-0 flex-1 items-center gap-3 pl-4 sm:pl-6 xl:h-auto xl:pl-0">
          <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open navigation">
                <Menu />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64 border-sidebar-border bg-sidebar p-0">
              <SheetTitle className="sr-only">Navigation</SheetTitle>
              <SheetDescription className="sr-only">Views of the application</SheetDescription>
              <SidebarNav onNavigate={() => setMenuOpen(false)} />
            </SheetContent>
          </Sheet>

          <div className="lg:hidden">
            <Brand />
          </div>

          <div className="hidden min-w-0 lg:block">
            <h1 className="truncate text-[15px] font-semibold tracking-tight text-foreground">{page.label}</h1>
            <p className="truncate text-xs text-muted-foreground">{page.description}</p>
          </div>
        </div>

        <div className="flex h-16 items-center pr-4 sm:pr-6 xl:order-last xl:h-auto xl:pr-0">
          <DataStatus />
        </div>

        {page.filtered ? (
          <div className="w-full border-t px-4 py-2.5 sm:px-6 xl:w-auto xl:border-t-0 xl:p-0">
            <FilterBar />
          </div>
        ) : null}
      </div>
    </header>
  )
}

function PageHeading() {
  const { pathname } = useLocation()
  const page = findNavItem(pathname)
  return (
    <div className="mb-5 lg:hidden">
      <h1 className="text-lg font-semibold tracking-tight text-foreground">{page.label}</h1>
      <p className="text-xs text-muted-foreground">{page.description}</p>
    </div>
  )
}

/** One line that states the slice of data every block of the page is showing. */
function ContextLine() {
  const { pathname } = useLocation()
  const { start, end, units, dimensions, activePreset } = useFilters()
  if (!findNavItem(pathname).filtered) return null
  const unitNames =
    units.length === 0
      ? 'All business units'
      : dimensions.business_units
          .filter((unit) => units.includes(unit.code))
          .map((unit) => unit.name)
          .join(', ')
  return (
    <p className="mb-5 text-xs text-muted-foreground" data-testid="context-line">
      <span className="font-medium text-foreground/90">
        {activePreset ? `${activePreset.label} · ` : ''}
        {formatMonth(start)} – {formatMonth(end)}
      </span>
      <span className="mx-2 text-subtle">/</span>
      {unitNames}
      <span className="mx-2 text-subtle">/</span>
      {dimensions.currency}
    </p>
  )
}

function ShellSkeleton() {
  return (
    <div className="flex min-h-svh" role="status" aria-label="Loading application">
      <div className="hidden w-60 border-r border-sidebar-border bg-sidebar p-5 lg:block">
        <Skeleton className="h-7 w-36" />
        <div className="mt-10 space-y-3">
          {Array.from({ length: 8 }, (_, index) => (
            <Skeleton key={index} className="h-7 w-full" />
          ))}
        </div>
      </div>
      <div className="flex-1 p-6">
        <Skeleton className="h-9 w-64" />
        <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-36 rounded-xl" />
          ))}
        </div>
        <Skeleton className="mt-4 h-80 rounded-xl" />
      </div>
    </div>
  )
}

/** Application frame: sidebar, top bar with the global filters, and the routed view. */
export function AppShell() {
  const dimensions = useDimensions()

  if (dimensions.isError) {
    return (
      <div className="flex min-h-svh items-center justify-center p-6">
        <div className="w-full max-w-md">
          <StateMessage
            tone="error"
            icon={<CircleAlert />}
            title="The application could not load its data"
            hint={dimensions.error instanceof Error ? dimensions.error.message : 'Unexpected error.'}
            minHeight={260}
            action={
              <Button variant="outline" size="sm" onClick={() => void dimensions.refetch()}>
                <RotateCw /> Try again
              </Button>
            }
          />
        </div>
      </div>
    )
  }
  if (!dimensions.data) return <ShellSkeleton />

  return (
    <FiltersProvider dimensions={dimensions.data}>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground"
      >
        Skip to content
      </a>
      <div className="flex min-h-svh">
        <aside className="sticky top-0 hidden h-svh w-60 shrink-0 border-r border-sidebar-border bg-sidebar lg:block">
          <SidebarNav />
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar />
          <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1480px] flex-1 px-4 py-6 outline-none sm:px-6">
            <PageHeading />
            <ContextLine />
            <Outlet />
          </main>
        </div>
      </div>
    </FiltersProvider>
  )
}
