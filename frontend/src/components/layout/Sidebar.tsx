import { NavLink } from 'react-router'

import { NAVIGATION } from '@/components/layout/navigation'
import { useFilters } from '@/lib/filters'
import { cn } from '@/lib/utils'

export function BrandMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 28 28" className={className} aria-hidden>
      <rect width="28" height="28" rx="7" fill="#0f2a44" />
      <path d="M7 19.5V13m5 6.5V9.5m5 10v-5m4 5V7.5" stroke="#38bdf8" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  )
}

export function Brand() {
  return (
    <div className="flex items-center gap-2.5">
      <BrandMark className="size-7 shrink-0" />
      <div className="leading-none">
        <p className="text-[11px] font-semibold tracking-[0.18em] text-foreground">FINANCIAL</p>
        <p className="mt-1 text-[11px] font-semibold tracking-[0.18em] text-brand">INTELLIGENCE</p>
      </div>
    </div>
  )
}

/** Primary navigation. Links keep the active filters, so switching views keeps the context. */
export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const { search, dimensions } = useFilters()
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 shrink-0 items-center px-5">
        <Brand />
      </div>

      <nav aria-label="Primary" className="scrollbar-thin flex-1 overflow-y-auto px-3 pb-4">
        {NAVIGATION.map((section) => (
          <div key={section.title} className="mt-5 first:mt-2">
            <p className="px-2 pb-1.5 text-[10px] font-semibold tracking-[0.14em] text-subtle uppercase">
              {section.title}
            </p>
            <ul className="space-y-0.5">
              {section.items.map((item) => (
                <li key={item.path}>
                  <NavLink
                    to={{ pathname: item.path, search: item.filtered ? search : '' }}
                    end={item.path === '/'}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        'group relative flex h-9 items-center gap-2.5 rounded-lg px-2.5 text-[13px] font-medium transition-colors',
                        isActive
                          ? 'bg-sidebar-accent text-foreground'
                          : 'text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-foreground',
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <span
                          aria-hidden
                          className={cn(
                            'absolute top-2 bottom-2 left-0 w-0.5 rounded-full bg-brand transition-opacity',
                            isActive ? 'opacity-100' : 'opacity-0',
                          )}
                        />
                        <item.icon
                          aria-hidden
                          className={cn('size-4 shrink-0', isActive ? 'text-brand' : 'text-subtle group-hover:text-muted-foreground')}
                        />
                        {item.label}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="shrink-0 border-t border-sidebar-border px-5 py-4">
        <p className="text-[11px] font-medium text-muted-foreground">{dimensions.company}</p>
        <p className="mt-0.5 text-[11px] leading-snug text-subtle">Fictional company · synthetic data</p>
      </div>
    </div>
  )
}
