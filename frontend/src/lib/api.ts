/**
 * API client. Response types come from the OpenAPI schema of the backend
 * (`npm run gen:api`), so the client cannot drift from the server contract.
 */
import type { components } from './api-schema'

type Schemas = components['schemas']

export type Favorability = 'favorable' | 'unfavorable' | 'on_target'
export type ComparisonMode = 'previous_year' | 'previous_period'

export type AppliedFilters = Schemas['AppliedFilters']
export type HealthResponse = Schemas['HealthResponse']
export type DimensionsResponse = Schemas['DimensionsResponse']
export type KpiCatalogResponse = Schemas['KpiCatalogResponse']
export type KpiDefinition = Schemas['KpiDefinition']
export type Kpi = Schemas['Kpi']
export type KpiSummaryResponse = Schemas['KpiSummaryResponse']
export type TimeSeriesPoint = Schemas['TimeSeriesPoint']
export type TimeSeriesResponse = Schemas['TimeSeriesResponse']
export type UnitTimeSeriesResponse = Schemas['UnitTimeSeriesResponse']
export type StatementLine = Schemas['StatementLine']
export type BudgetStatementResponse = Schemas['BudgetStatementResponse']
export type BudgetVarianceResponse = Schemas['BudgetVarianceResponse']
export type BudgetVarianceRow = Schemas['BudgetVarianceRow']
export type Measure = Schemas['Measure']
export type BudgetMatrixResponse = Schemas['BudgetMatrixResponse']
export type BudgetMatrixCell = Schemas['BudgetMatrixCell']
export type ProfitabilityResponse = Schemas['ProfitabilityResponse']
export type ProfitabilityRow = Schemas['ProfitabilityRow']
export type ExpenseBreakdownResponse = Schemas['ExpenseBreakdownResponse']
export type ExpenseRow = Schemas['ExpenseRow']
export type ExpenseMatrixResponse = Schemas['ExpenseMatrixResponse']
export type BridgeResponse = Schemas['BridgeResponse']
export type PvmResponse = Schemas['PvmResponse']
export type MarginDriversResponse = Schemas['MarginDriversResponse']
export type AnomaliesResponse = Schemas['AnomaliesResponse']
export type Anomaly = Schemas['Anomaly']
export type InsightsResponse = Schemas['InsightsResponse']
export type Insight = Schemas['Insight']
export type MonthlyRecordsResponse = Schemas['MonthlyRecordsResponse']
export type MonthlyRecord = Schemas['MonthlyRecord']
export type DataQualityResponse = Schemas['DataQualityResponse']
export type QualityCheckItem = Schemas['QualityCheckItem']

export type QueryValue = string | number | boolean | string[] | null | undefined
export type QueryParams = Record<string, QueryValue>

const BASE_URL = `${import.meta.env.VITE_API_BASE_URL ?? ''}/api/v1`

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Builds a query string; arrays become repeated parameters (business_unit=A&business_unit=B). */
export function buildQuery(params: QueryParams): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === '') continue
    if (Array.isArray(value)) value.forEach((item) => search.append(key, item))
    else search.append(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

export function apiUrl(path: string, params: QueryParams = {}): string {
  return `${BASE_URL}${path}${buildQuery(params)}`
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail
      if (typeof detail === 'string') return detail
      if (Array.isArray(detail)) {
        return detail
          .map((item: { msg?: string; loc?: unknown[] }) =>
            [item.loc?.slice(1).join('.'), item.msg].filter(Boolean).join(': '),
          )
          .join('; ')
      }
    }
  } catch {
    // The body was not JSON: fall through to the generic message.
  }
  return `The request failed (HTTP ${response.status}).`
}

export async function apiGet<T>(path: string, params: QueryParams = {}, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(apiUrl(path, params), { signal, headers: { Accept: 'application/json' } })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'The API is unreachable. Check that the backend is running.')
  }
  if (!response.ok) throw new ApiError(response.status, await errorMessage(response))
  return (await response.json()) as T
}
