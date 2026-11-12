import { lazy, Suspense, type ComponentType, type LazyExoticComponent } from 'react'
import { Navigate, Route, Routes } from 'react-router'

import { AppShell } from '@/components/layout/AppShell'
import { Skeleton } from '@/components/ui/skeleton'

// Views are split into their own chunks: the charting library loads only where it is used.
const VIEWS: { path: string; Component: LazyExoticComponent<ComponentType> }[] = [
  { path: '/', Component: lazy(() => import('@/pages/Overview')) },
  { path: '/revenue', Component: lazy(() => import('@/pages/Revenue')) },
  { path: '/costs', Component: lazy(() => import('@/pages/Costs')) },
  { path: '/profitability', Component: lazy(() => import('@/pages/Profitability')) },
  { path: '/budget', Component: lazy(() => import('@/pages/Budget')) },
  { path: '/trends', Component: lazy(() => import('@/pages/Trends')) },
  { path: '/data-quality', Component: lazy(() => import('@/pages/DataQuality')) },
  { path: '/methodology', Component: lazy(() => import('@/pages/Methodology')) },
]

function PageFallback() {
  return (
    <div role="status" aria-label="Loading view" className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-40 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-96 rounded-xl" />
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        {VIEWS.map(({ path, Component }) => (
          <Route
            key={path}
            path={path}
            element={
              <Suspense fallback={<PageFallback />}>
                <Component />
              </Suspense>
            }
          />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
