"""Typed API responses.

Conventions: months are 'YYYY-MM' strings, amounts are USD, ratios are fractions
(0.25 = 25%) and a null value means "not defined" (for example a margin with zero
revenue, or a comparison whose period is outside the available data).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Favorability = Literal["favorable", "unfavorable", "on_target"]
ComparisonMode = Literal["previous_year", "previous_period"]
Unit = Literal["currency", "percent", "number"]


# --------------------------------------------------------------------------- #
# Shared
# --------------------------------------------------------------------------- #
class AppliedFilters(BaseModel):
    """The analysis context actually applied, echoed back with every analytic response."""

    start: str = Field(examples=["2025-01"])
    end: str = Field(examples=["2025-12"])
    months: int
    period_label: str
    business_units: list[str] = Field(description="Business unit codes; all units if empty")
    compare: ComparisonMode
    comparison_available: bool = Field(
        description="False when the comparison period falls outside the available data"
    )
    comparison_start: str | None = None
    comparison_end: str | None = None
    comparison_label: str | None = None


class Measure(BaseModel):
    """An actual amount compared with its budget."""

    actual: float
    budget: float
    variance: float = Field(description="actual - budget")
    variance_pct: float | None = Field(description="variance / |budget|")
    status: Favorability


# --------------------------------------------------------------------------- #
# Service and catalogues
# --------------------------------------------------------------------------- #
class DataStatus(BaseModel):
    loaded: bool
    last_successful_run_at: datetime | None = None
    period_start: str | None = None
    period_end: str | None = None
    synthetic: bool = True


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["up", "down"]
    version: str
    data: DataStatus


class BusinessUnitItem(BaseModel):
    code: str
    name: str
    sales_channel: str


class CategoryItem(BaseModel):
    code: str
    name: str
    product_count: int


class ProductItem(BaseModel):
    code: str
    name: str
    category_code: str
    category_name: str


class CostCenterItem(BaseModel):
    code: str
    name: str
    function_area: str


class AccountItem(BaseModel):
    code: str
    name: str
    account_type: str
    account_group: str
    cost_behavior: str


class AvailablePeriod(BaseModel):
    start: str
    end: str
    months: list[str]
    fiscal_years: list[int]


class DimensionsResponse(BaseModel):
    currency: str
    company: str
    synthetic: bool
    period: AvailablePeriod
    business_units: list[BusinessUnitItem]
    categories: list[CategoryItem]
    products: list[ProductItem]
    cost_centers: list[CostCenterItem]
    accounts: list[AccountItem]


class KpiDefinition(BaseModel):
    id: str
    name: str
    formula: str
    unit: str
    grain: str
    filters: str
    null_handling: str
    interpretation: str
    limitations: str


class KpiCatalogResponse(BaseModel):
    kpis: list[KpiDefinition]


# --------------------------------------------------------------------------- #
# Executive KPIs and time series
# --------------------------------------------------------------------------- #
class Kpi(BaseModel):
    id: str
    label: str
    unit: Unit
    higher_is_better: bool
    value: float | None
    comparison_value: float | None = None
    change: float | None = Field(
        default=None, description="value - comparison (percentage points for percent KPIs)"
    )
    change_pct: float | None = Field(
        default=None, description="Relative change; null for percent KPIs"
    )
    comparison_status: Favorability | None = None
    budget_value: float | None = None
    budget_variance: float | None = None
    budget_variance_pct: float | None = None
    budget_status: Favorability | None = None
    sparkline: list[float | None] = Field(description="Monthly values across the period")


class KpiSummaryResponse(BaseModel):
    filters: AppliedFilters
    kpis: list[Kpi]


class TimeSeriesPoint(BaseModel):
    month: str
    net_revenue: float
    direct_costs: float
    gross_profit: float
    operating_expenses: float
    operating_income: float
    gross_margin: float | None
    operating_margin: float | None
    budget_net_revenue: float
    budget_direct_costs: float
    budget_operating_expenses: float
    budget_operating_income: float
    revenue_mom_pct: float | None = Field(description="Growth vs the previous month")
    revenue_yoy_pct: float | None = Field(description="Growth vs the same month a year earlier")
    operating_income_mom_pct: float | None
    operating_income_yoy_pct: float | None
    revenue_rolling_3m: float | None = Field(description="Trailing three-month average")


class TimeSeriesResponse(BaseModel):
    filters: AppliedFilters
    points: list[TimeSeriesPoint]


class UnitSeriesPoint(BaseModel):
    month: str
    net_revenue: float
    gross_profit: float
    operating_income: float
    gross_margin: float | None
    operating_margin: float | None


class UnitSeries(BaseModel):
    key: str
    label: str
    points: list[UnitSeriesPoint]


class UnitTimeSeriesResponse(BaseModel):
    filters: AppliedFilters
    series: list[UnitSeries]


# --------------------------------------------------------------------------- #
# Budget versus actual
# --------------------------------------------------------------------------- #
class StatementLine(BaseModel):
    key: str
    label: str
    level: Literal["account", "subtotal"]
    account_type: str | None
    account_group: str | None
    higher_is_better: bool
    actual: float
    budget: float
    variance: float
    variance_pct: float | None
    status: Favorability
    profit_impact: float = Field(description="Effect of the variance on operating income")
    pct_of_revenue: float | None


class BudgetStatementResponse(BaseModel):
    filters: AppliedFilters
    lines: list[StatementLine]


class BudgetVarianceRow(BaseModel):
    key: str
    label: str
    net_revenue: Measure
    direct_costs: Measure
    operating_expenses: Measure
    operating_income: Measure


class BudgetVarianceResponse(BaseModel):
    filters: AppliedFilters
    group_by: Literal["month", "business_unit"]
    rows: list[BudgetVarianceRow]


class BudgetMatrixCell(BaseModel):
    business_unit_code: str
    business_unit_name: str
    account_code: str
    account_name: str
    account_type: str
    actual: float
    budget: float
    variance: float
    variance_pct: float | None
    status: Favorability
    profit_impact: float


class BudgetMatrixResponse(BaseModel):
    filters: AppliedFilters
    cells: list[BudgetMatrixCell]


# --------------------------------------------------------------------------- #
# Profitability and expenses
# --------------------------------------------------------------------------- #
class ProfitabilityRow(BaseModel):
    key: str
    label: str
    parent_key: str | None = None
    parent_label: str | None = None
    units: float
    gross_sales: float
    discounts: float
    discount_rate: float | None
    net_revenue: float
    revenue_share: float | None
    direct_costs: float
    gross_profit: float
    gross_margin: float | None
    operating_expenses: float | None = Field(
        default=None, description="Only when grouped by business unit without category filter"
    )
    operating_income: float | None = None
    operating_margin: float | None = None
    comparison_net_revenue: float | None = None
    revenue_change_pct: float | None = None
    comparison_gross_margin: float | None = None
    gross_margin_change: float | None = Field(default=None, description="Change in ratio points")


class ProfitabilityResponse(BaseModel):
    filters: AppliedFilters
    group_by: Literal["business_unit", "category", "product"]
    category: str | None
    rows: list[ProfitabilityRow]
    total: ProfitabilityRow


class ExpenseRow(BaseModel):
    key: str
    label: str
    actual: float
    share: float | None = Field(description="Share of total operating expenses")
    pct_of_revenue: float | None
    budget: float | None = Field(description="Null when the grouping has no budget (cost centre)")
    variance: float | None
    variance_pct: float | None
    status: Favorability | None
    comparison: float | None
    change_pct: float | None


class ExpenseBreakdownResponse(BaseModel):
    filters: AppliedFilters
    group_by: Literal["account", "account_group", "cost_center", "cost_behavior"]
    rows: list[ExpenseRow]
    total: ExpenseRow


class ExpenseMatrixCell(BaseModel):
    cost_center_code: str
    cost_center_name: str
    account_group: str
    amount: float


class ExpenseMatrixResponse(BaseModel):
    filters: AppliedFilters
    cost_centers: list[str]
    account_groups: list[str]
    cells: list[ExpenseMatrixCell]


# --------------------------------------------------------------------------- #
# Contribution analysis and anomalies
# --------------------------------------------------------------------------- #
class BridgeStepItem(BaseModel):
    key: str
    label: str
    kind: Literal["total", "effect"]
    amount: float


class BridgeResponse(BaseModel):
    filters: AppliedFilters
    basis: Literal["comparison", "budget"]
    available: bool
    base_label: str | None
    current_label: str | None
    total_change: float | None
    steps: list[BridgeStepItem]


class PvmRow(BaseModel):
    key: str
    label: str
    base_revenue: float
    current_revenue: float
    volume_effect: float
    mix_effect: float
    price_effect: float
    total_change: float


class PvmResponse(BaseModel):
    filters: AppliedFilters
    group_by: Literal["category", "business_unit"]
    available: bool
    rows: list[PvmRow]
    total: PvmRow | None


class MarginDriverRow(BaseModel):
    key: str
    label: str
    base_share: float | None
    current_share: float | None
    base_margin: float | None
    current_margin: float | None
    rate_effect: float
    mix_effect: float
    total_effect: float


class MarginDriversResponse(BaseModel):
    filters: AppliedFilters
    group_by: Literal["category", "business_unit"]
    available: bool
    base_margin: float | None
    current_margin: float | None
    margin_change: float | None
    rate_effect: float | None
    mix_effect: float | None
    rows: list[MarginDriverRow]


class Anomaly(BaseModel):
    month: str
    business_unit_code: str
    business_unit_name: str
    account_code: str
    account_name: str
    account_type: str
    actual: float
    budget: float
    variance: float
    variance_pct: float
    typical_variance_pct: float = Field(description="Median variance % of the series")
    robust_z: float = Field(description="Modified z-score (median / MAD)")
    status: Favorability
    is_material: bool
    materiality_threshold: float


class AnomalyMethod(BaseModel):
    signal: str
    score: str
    z_threshold: float
    materiality: str
    series_evaluated: int
    months_of_history: int


class AnomaliesResponse(BaseModel):
    filters: AppliedFilters
    method: AnomalyMethod
    anomalies: list[Anomaly]


class Evidence(BaseModel):
    label: str
    value: float | None
    unit: Unit


class Insight(BaseModel):
    id: str
    category: Literal["performance", "budget", "expenses", "profitability", "trend", "anomaly"]
    tone: Literal["positive", "negative", "neutral"]
    title: str
    detail: str
    evidence: list[Evidence]


class InsightsResponse(BaseModel):
    filters: AppliedFilters
    insights: list[Insight]


# --------------------------------------------------------------------------- #
# Analytical table and data quality
# --------------------------------------------------------------------------- #
class MonthlyRecord(BaseModel):
    month: str
    business_unit_code: str
    business_unit_name: str
    net_revenue: float
    direct_costs: float
    gross_profit: float
    gross_margin: float | None
    operating_expenses: float
    operating_income: float
    operating_margin: float | None
    budget_net_revenue: float
    revenue_variance_pct: float | None
    budget_operating_income: float
    operating_income_variance: float


class Pagination(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class MonthlyRecordsResponse(BaseModel):
    filters: AppliedFilters
    pagination: Pagination
    sort_by: str
    sort_dir: Literal["asc", "desc"]
    rows: list[MonthlyRecord]


class EtlRunItem(BaseModel):
    run_id: int
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float | None
    status: str
    source_seed: int | None
    generator_version: str | None
    data_period_start: date | None
    data_period_end: date | None
    error_message: str | None


class TableLoadItem(BaseModel):
    target_table: str
    source_file: str
    rows_read: int
    rows_standardized: int
    rows_rejected: int
    rows_deduplicated: int
    rows_loaded: int


class QualityCheckItem(BaseModel):
    check_code: str
    check_name: str
    dataset: str
    quality_dimension: str
    stage: str
    severity: str
    status: str
    rows_checked: int
    rows_failed: int
    details: dict[str, Any] | None


class QualitySummary(BaseModel):
    total_checks: int
    passed: int
    warnings: int
    failed: int
    rows_read: int
    rows_loaded: int
    rows_rejected: int
    rows_deduplicated: int
    load_rate: float | None


class DataQualityResponse(BaseModel):
    latest_run: EtlRunItem | None
    summary: QualitySummary | None
    table_loads: list[TableLoadItem]
    checks: list[QualityCheckItem]
    table_row_counts: dict[str, int]
    recent_runs: list[EtlRunItem]
