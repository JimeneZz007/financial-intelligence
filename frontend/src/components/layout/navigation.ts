import {
  BookOpenText,
  CircleDollarSign,
  LayoutDashboard,
  type LucideIcon,
  Percent,
  ReceiptText,
  ShieldCheck,
  Sparkles,
  Target,
} from 'lucide-react'

export interface NavItem {
  path: string
  label: string
  description: string
  icon: LucideIcon
  /** Whether the global filters apply to the view. */
  filtered: boolean
}

export interface NavSection {
  title: string
  items: NavItem[]
}

export const NAVIGATION: NavSection[] = [
  {
    title: 'Analysis',
    items: [
      {
        path: '/',
        label: 'Overview',
        description: 'Executive summary of results against plan',
        icon: LayoutDashboard,
        filtered: true,
      },
      {
        path: '/revenue',
        label: 'Revenue',
        description: 'Where sales come from and what moved them',
        icon: CircleDollarSign,
        filtered: true,
      },
      {
        path: '/costs',
        label: 'Costs & Expenses',
        description: 'Direct costs and operating expenses',
        icon: ReceiptText,
        filtered: true,
      },
      {
        path: '/profitability',
        label: 'Profitability',
        description: 'Margins by unit and category, and their drivers',
        icon: Percent,
        filtered: true,
      },
      {
        path: '/budget',
        label: 'Budget vs Actual',
        description: 'Execution against the approved budget',
        icon: Target,
        filtered: true,
      },
      {
        path: '/trends',
        label: 'Trends & Insights',
        description: 'Growth, unusual months and computed findings',
        icon: Sparkles,
        filtered: true,
      },
    ],
  },
  {
    title: 'Governance',
    items: [
      {
        path: '/data-quality',
        label: 'Data Quality',
        description: 'Latest pipeline run and data-quality checks',
        icon: ShieldCheck,
        filtered: false,
      },
      {
        path: '/methodology',
        label: 'Methodology',
        description: 'Data, model, KPI definitions and methods',
        icon: BookOpenText,
        filtered: false,
      },
    ],
  },
]

export const NAV_ITEMS: NavItem[] = NAVIGATION.flatMap((section) => section.items)

export function findNavItem(pathname: string): NavItem {
  return NAV_ITEMS.find((item) => item.path === pathname) ?? NAV_ITEMS[0]!
}
