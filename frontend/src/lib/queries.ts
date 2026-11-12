/** Data hooks: one per API endpoint, all driven by the global filters. */
import { keepPreviousData, useQuery, type UseQueryResult } from '@tanstack/react-query'

import {
  apiGet,
  type AnomaliesResponse,
  type BridgeResponse,
  type BudgetMatrixResponse,
  type BudgetStatementResponse,
  type BudgetVarianceResponse,
  type DataQualityResponse,
  type DimensionsResponse,
  type ExpenseBreakdownResponse,
  type ExpenseMatrixResponse,
  type HealthResponse,
  type InsightsResponse,
  type KpiCatalogResponse,
  type KpiSummaryResponse,
  type MarginDriversResponse,
  type MonthlyRecordsResponse,
  type ProfitabilityResponse,
  type PvmResponse,
  type QueryParams,
  type TimeSeriesResponse,
  type UnitTimeSeriesResponse,
} from './api'
import { useFilters } from './filters'

/**
 * Query scoped by the global filters. While a new slice loads, the previous one stays on
 * screen (`placeholderData`), so views never flash a skeleton on a filter change.
 */
function useAnalytics<T>(path: string, extra: QueryParams = {}): UseQueryResult<T> {
  const { apiParams } = useFilters()
  const params = { ...apiParams, ...extra }
  return useQuery({
    queryKey: [path, params],
    queryFn: ({ signal }) => apiGet<T>(path, params, signal),
    placeholderData: keepPreviousData,
  })
}

// --- not filtered ---------------------------------------------------------------------
export const useDimensions = () =>
  useQuery({
    queryKey: ['/dimensions'],
    queryFn: ({ signal }) => apiGet<DimensionsResponse>('/dimensions', {}, signal),
    staleTime: Infinity,
  })

export const useHealth = () =>
  useQuery({
    queryKey: ['/health'],
    queryFn: ({ signal }) => apiGet<HealthResponse>('/health', {}, signal),
    refetchInterval: 60_000,
    retry: false,
  })

export const useKpiCatalog = () =>
  useQuery({
    queryKey: ['/kpi-catalog'],
    queryFn: ({ signal }) => apiGet<KpiCatalogResponse>('/kpi-catalog', {}, signal),
    staleTime: Infinity,
  })

export const useDataQuality = () =>
  useQuery({
    queryKey: ['/data-quality'],
    queryFn: ({ signal }) => apiGet<DataQualityResponse>('/data-quality', {}, signal),
  })

// --- filtered -------------------------------------------------------------------------
export const useKpis = () => useAnalytics<KpiSummaryResponse>('/kpis/summary')
export const useTimeSeries = () => useAnalytics<TimeSeriesResponse>('/timeseries')
export const useUnitSeries = () => useAnalytics<UnitTimeSeriesResponse>('/timeseries/business-units')
export const useBudgetStatement = () => useAnalytics<BudgetStatementResponse>('/budget/statement')
export const useBudgetVariance = (groupBy: 'month' | 'business_unit') =>
  useAnalytics<BudgetVarianceResponse>('/budget/variance', { group_by: groupBy })
export const useBudgetMatrix = () => useAnalytics<BudgetMatrixResponse>('/budget/matrix')
export const useProfitability = (
  groupBy: 'business_unit' | 'category' | 'product',
  category?: string | null,
) => useAnalytics<ProfitabilityResponse>('/profitability', { group_by: groupBy, category })
export const useExpenseBreakdown = (
  groupBy: 'account' | 'account_group' | 'cost_center' | 'cost_behavior',
) => useAnalytics<ExpenseBreakdownResponse>('/expenses/breakdown', { group_by: groupBy })
export const useExpenseMatrix = () => useAnalytics<ExpenseMatrixResponse>('/expenses/matrix')
export const useBridge = (basis: 'comparison' | 'budget') =>
  useAnalytics<BridgeResponse>('/analysis/operating-income-bridge', { basis })
export const usePvm = (groupBy: 'category' | 'business_unit') =>
  useAnalytics<PvmResponse>('/analysis/price-volume-mix', { group_by: groupBy })
export const useMarginDrivers = (groupBy: 'category' | 'business_unit') =>
  useAnalytics<MarginDriversResponse>('/analysis/margin-drivers', { group_by: groupBy })
export const useAnomalies = (includeImmaterial: boolean) =>
  useAnalytics<AnomaliesResponse>('/analysis/anomalies', { include_immaterial: includeImmaterial })
export const useInsights = () => useAnalytics<InsightsResponse>('/insights')

export interface RecordsQuery {
  page: number
  pageSize: number
  sortBy: string
  sortDir: 'asc' | 'desc'
  revenueVsBudget: 'all' | 'above' | 'below'
}

export const useMonthlyRecords = (query: RecordsQuery) =>
  useAnalytics<MonthlyRecordsResponse>('/records/monthly', {
    page: query.page,
    page_size: query.pageSize,
    sort_by: query.sortBy,
    sort_dir: query.sortDir,
    revenue_vs_budget: query.revenueVsBudget,
  })
