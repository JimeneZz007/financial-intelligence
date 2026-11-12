import type { DimensionsResponse, Kpi, KpiSummaryResponse } from '@/lib/api'

const MONTHS = Array.from({ length: 36 }, (_, index) => {
  const year = 2023 + Math.floor(index / 12)
  return `${year}-${String((index % 12) + 1).padStart(2, '0')}`
})

export const dimensions: DimensionsResponse = {
  currency: 'USD',
  company: 'Grupo Comercial Altamira',
  synthetic: true,
  period: { start: '2023-01', end: '2025-12', months: MONTHS, fiscal_years: [2023, 2024, 2025] },
  business_units: [
    { code: 'RET', name: 'Retail Stores', sales_channel: 'Physical stores' },
    { code: 'ECM', name: 'E-commerce', sales_channel: 'Online' },
    { code: 'WHS', name: 'Wholesale Distribution', sales_channel: 'Distributors' },
    { code: 'COR', name: 'Corporate Solutions', sales_channel: 'B2B contracts' },
  ],
  categories: [
    { code: 'ELE', name: 'Electronics', product_count: 6 },
    { code: 'OFF', name: 'Office Supplies', product_count: 6 },
  ],
  products: [{ code: 'ELE-001', name: 'Business Laptop 14"', category_code: 'ELE', category_name: 'Electronics' }],
  cost_centers: [{ code: 'SAL', name: 'Sales & Commercial', function_area: 'Commercial' }],
  accounts: [
    { code: '4000', name: 'Net Sales Revenue', account_type: 'REVENUE', account_group: 'Revenue', cost_behavior: 'NOT_APPLICABLE' },
  ],
}

export function kpi(overrides: Partial<Kpi> = {}): Kpi {
  return {
    id: 'net_revenue',
    label: 'Net revenue',
    unit: 'currency',
    higher_is_better: true,
    value: 59_053_741.75,
    comparison_value: 52_097_564.14,
    change: 6_956_177.61,
    change_pct: 0.133522,
    comparison_status: 'favorable',
    budget_value: 58_697_700,
    budget_variance: 356_041.75,
    budget_variance_pct: 0.006066,
    budget_status: 'favorable',
    sparkline: [4.4e6, 3.5e6, 4.6e6, 4.4e6, 4.9e6, 4.5e6, 5.1e6, 5.3e6, 4.9e6, 5.3e6, 5.8e6, 6.1e6],
    ...overrides,
  }
}

/** A KPI summary whose net revenue depends on the units requested, to prove filters reach the API. */
export function kpiSummary(units: string[]): KpiSummaryResponse {
  const revenue = units.length === 0 ? 59_053_741.75 : units.length * 10_000_000
  return {
    filters: {
      start: '2025-01',
      end: '2025-12',
      months: 12,
      period_label: 'Jan 2025 - Dec 2025',
      business_units: units,
      compare: 'previous_year',
      comparison_available: true,
      comparison_start: '2024-01',
      comparison_end: '2024-12',
      comparison_label: 'Jan 2024 - Dec 2024',
    },
    kpis: [
      kpi({ value: revenue }),
      kpi({ id: 'direct_costs', label: 'Direct costs', higher_is_better: false, value: 40_807_923, change: 5_488_659, change_pct: 0.155401, comparison_status: 'unfavorable', budget_status: 'unfavorable' }),
      kpi({ id: 'operating_income', label: 'Operating income', value: 3_991_969.68, change_pct: 0.156965 }),
      kpi({ id: 'operating_margin', label: 'Operating margin', unit: 'percent', value: 0.067599, comparison_value: 0.066229, change: 0.00137, change_pct: null, budget_value: 0.08331, budget_variance: -0.015711, budget_variance_pct: null, budget_status: 'unfavorable' }),
    ],
  }
}
