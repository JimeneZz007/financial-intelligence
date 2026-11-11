"""API integration tests against PostgreSQL loaded by the real pipeline.

Figures are checked three ways: against the pandas oracle (generator frames), against
direct SQL on the fact tables, and for internal consistency between endpoints.
"""

from __future__ import annotations

import io
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from backend.app.repositories import warehouse
from tests.api.conftest import API, Oracle

pytestmark = pytest.mark.integration

FY2025 = {"start": "2025-01", "end": "2025-12"}
CENT = 0.011  # amounts are rounded to cents in responses


def get(client: TestClient, path: str, **params: Any) -> Any:
    response = client.get(f"{API}{path}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def kpis(client: TestClient, **params: Any) -> dict[str, dict[str, Any]]:
    return {kpi["id"]: kpi for kpi in get(client, "/kpis/summary", **params)["kpis"]}


# --------------------------------------------------------------------------- #
# Service, catalogues and documentation
# --------------------------------------------------------------------------- #
def test_health_reports_database_and_data_status(client: TestClient) -> None:
    body = get(client, "/health")
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert body["data"] == {
        "loaded": True,
        "last_successful_run_at": body["data"]["last_successful_run_at"],
        "period_start": "2023-01",
        "period_end": "2025-12",
        "synthetic": True,
    }
    assert body["data"]["last_successful_run_at"] is not None


def test_dimensions_catalogue(client: TestClient) -> None:
    body = get(client, "/dimensions")
    assert body["synthetic"] is True
    assert body["currency"] == "USD"
    assert [unit["code"] for unit in body["business_units"]] == ["RET", "ECM", "WHS", "COR"]
    assert len(body["categories"]) == 5
    assert sum(category["product_count"] for category in body["categories"]) == 30
    assert len(body["products"]) == 30
    assert len(body["cost_centers"]) == 6
    assert len(body["accounts"]) == 13
    assert body["period"]["start"] == "2023-01"
    assert body["period"]["end"] == "2025-12"
    assert len(body["period"]["months"]) == 36
    assert body["period"]["fiscal_years"] == [2023, 2024, 2025]


def test_openapi_documents_every_endpoint(client: TestClient) -> None:
    schema = client.get(f"{API}/openapi.json").json()
    paths = set(schema["paths"])
    expected = {
        "/health",
        "/dimensions",
        "/kpi-catalog",
        "/data-quality",
        "/kpis/summary",
        "/timeseries",
        "/timeseries/business-units",
        "/budget/statement",
        "/budget/variance",
        "/budget/matrix",
        "/profitability",
        "/expenses/breakdown",
        "/expenses/matrix",
        "/analysis/operating-income-bridge",
        "/analysis/price-volume-mix",
        "/analysis/margin-drivers",
        "/analysis/anomalies",
        "/insights",
        "/records/monthly",
        "/exports/{dataset}",
    }
    assert {f"{API}{path}" for path in expected} == paths
    for path, operations in schema["paths"].items():
        assert operations["get"].get("summary"), f"{path} has no summary"
    assert client.get(f"{API}/docs").status_code == 200


def test_kpi_catalog_defines_every_headline_kpi(client: TestClient) -> None:
    catalog = {kpi["id"]: kpi for kpi in get(client, "/kpi-catalog")["kpis"]}
    for kpi_id in kpis(client, **FY2025):
        assert kpi_id in catalog
    for definition in catalog.values():
        assert all(definition[field] for field in definition), definition["id"]


# --------------------------------------------------------------------------- #
# Executive KPIs: triangulation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("start", "end", "units"),
    [
        ("2023-01", "2025-12", []),
        ("2025-01", "2025-12", []),
        ("2024-04", "2024-06", ["WHS"]),
        ("2025-03", "2025-03", ["ECM", "RET"]),
        ("2023-11", "2024-02", ["COR"]),
    ],
)
def test_kpis_match_the_independent_oracle(
    client: TestClient, oracle: Oracle, start: str, end: str, units: list[str]
) -> None:
    result = kpis(client, start=start, end=end, business_unit=units)
    actual = oracle.actual(start, end, units)
    planned = oracle.planned(start, end, units)
    for kpi_id, expected in actual.items():
        tolerance = 1e-6 if kpi_id.endswith("margin") else CENT
        assert result[kpi_id]["value"] == pytest.approx(expected, abs=tolerance), kpi_id
        assert result[kpi_id]["budget_value"] == pytest.approx(planned[kpi_id], abs=tolerance), (
            kpi_id
        )


def test_kpis_match_direct_sql_on_the_fact_tables(
    client: TestClient, loaded_engine: Engine
) -> None:
    sql = """
        SELECT
          (SELECT SUM(s.net_sales_amount) FROM fact_sales s
            JOIN dim_business_unit b USING (business_unit_key)
            WHERE s.date_key BETWEEN 20240101 AND 20241231 AND b.business_unit_code = 'ECM'),
          (SELECT SUM(s.cogs_amount) FROM fact_sales s
            JOIN dim_business_unit b USING (business_unit_key)
            WHERE s.date_key BETWEEN 20240101 AND 20241231 AND b.business_unit_code = 'ECM'),
          (SELECT SUM(e.amount) FROM fact_operating_expenses e
            JOIN dim_business_unit b USING (business_unit_key)
            WHERE e.date_key BETWEEN 20240101 AND 20241231 AND b.business_unit_code = 'ECM')
    """
    with loaded_engine.connect() as connection:
        revenue, cogs, opex = (float(v) for v in connection.execute(text(sql)).one())
    result = kpis(client, start="2024-01", end="2024-12", business_unit="ECM")
    assert result["net_revenue"]["value"] == pytest.approx(revenue, abs=CENT)
    assert result["direct_costs"]["value"] == pytest.approx(cogs, abs=CENT)
    assert result["operating_expenses"]["value"] == pytest.approx(opex, abs=CENT)
    assert result["operating_income"]["value"] == pytest.approx(revenue - cogs - opex, abs=CENT)


def test_kpi_comparison_and_budget_fields(client: TestClient, oracle: Oracle) -> None:
    result = kpis(client, **FY2025, compare="previous_year")
    current, previous = oracle.actual("2025-01", "2025-12"), oracle.actual("2024-01", "2024-12")
    planned = oracle.planned("2025-01", "2025-12")

    revenue = result["net_revenue"]
    assert revenue["comparison_value"] == pytest.approx(previous["net_revenue"], abs=CENT)
    assert revenue["change"] == pytest.approx(
        current["net_revenue"] - previous["net_revenue"], abs=2 * CENT
    )
    assert revenue["change_pct"] == pytest.approx(
        current["net_revenue"] / previous["net_revenue"] - 1, abs=1e-6
    )
    assert revenue["comparison_status"] == "favorable"
    assert revenue["budget_variance_pct"] == pytest.approx(
        current["net_revenue"] / planned["net_revenue"] - 1, abs=1e-6
    )

    # Costs rising is unfavorable even though the number went up.
    assert result["direct_costs"]["change"] > 0
    assert result["direct_costs"]["comparison_status"] == "unfavorable"

    # Margins are compared in percentage points and have no relative change.
    margin = result["gross_margin"]
    assert margin["unit"] == "percent"
    assert margin["change_pct"] is None
    assert margin["change"] == pytest.approx(
        current["gross_margin"] - previous["gross_margin"], abs=1e-6
    )
    assert len(revenue["sparkline"]) == 12
    assert sum(revenue["sparkline"]) == pytest.approx(current["net_revenue"], abs=12 * CENT)


def test_comparison_is_null_when_its_period_has_no_data(client: TestClient) -> None:
    body = get(client, "/kpis/summary", start="2023-01", end="2023-12", compare="previous_year")
    assert body["filters"]["comparison_available"] is False
    assert body["filters"]["comparison_start"] is None
    for kpi in body["kpis"]:
        assert kpi["comparison_value"] is None
        assert kpi["change"] is None
        assert kpi["comparison_status"] is None
        assert kpi["budget_value"] is not None  # the budget does not depend on history


def test_previous_period_comparison(client: TestClient, oracle: Oracle) -> None:
    body = get(client, "/kpis/summary", start="2025-07", end="2025-09", compare="previous_period")
    assert body["filters"]["comparison_start"] == "2025-04"
    assert body["filters"]["comparison_end"] == "2025-06"
    revenue = next(kpi for kpi in body["kpis"] if kpi["id"] == "net_revenue")
    assert revenue["comparison_value"] == pytest.approx(
        oracle.actual("2025-04", "2025-06")["net_revenue"], abs=CENT
    )


# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #
def test_business_units_add_up_to_the_company_total(client: TestClient) -> None:
    total = kpis(client, **FY2025)
    by_unit = [kpis(client, **FY2025, business_unit=code) for code in ("RET", "ECM", "WHS", "COR")]
    for kpi_id in ("net_revenue", "direct_costs", "operating_expenses", "operating_income"):
        assert sum(unit[kpi_id]["value"] for unit in by_unit) == pytest.approx(
            total[kpi_id]["value"], abs=4 * CENT
        ), kpi_id


def test_filters_change_every_analytic_response(client: TestClient) -> None:
    for path in (
        "/kpis/summary",
        "/timeseries",
        "/budget/statement",
        "/profitability",
        "/expenses/breakdown",
        "/insights",
        "/records/monthly",
    ):
        company = get(client, path, **FY2025)
        retail = get(client, path, **FY2025, business_unit="RET")
        other_year = get(client, path, start="2024-01", end="2024-12")
        assert retail["filters"]["business_units"] == ["RET"], path
        assert company["filters"]["business_units"] == [], path
        strip = lambda body: {k: v for k, v in body.items() if k != "filters"}  # noqa: E731
        assert strip(company) != strip(retail), path
        assert strip(company) != strip(other_year), path


def test_selecting_every_unit_equals_no_filter(client: TestClient) -> None:
    everything = get(client, "/kpis/summary", **FY2025, business_unit=["RET", "ECM", "WHS", "COR"])
    unfiltered = get(client, "/kpis/summary", **FY2025)
    assert everything == unfiltered


def test_default_period_is_the_last_twelve_months(client: TestClient) -> None:
    filters = get(client, "/kpis/summary")["filters"]
    assert (filters["start"], filters["end"], filters["months"]) == ("2025-01", "2025-12", 12)


@pytest.mark.parametrize(
    ("params", "fragment"),
    [
        ({"start": "2025-13"}, "pattern"),
        ({"start": "2025-1"}, "pattern"),
        ({"start": "2025-06", "end": "2025-01"}, "start must not be after"),
        ({"start": "2026-01", "end": "2026-03"}, "outside the available data"),
        ({"start": "2022-06", "end": "2023-03"}, "outside the available data"),
        ({"business_unit": "XXX"}, "Unknown business unit"),
        ({"compare": "last_decade"}, "previous_year"),
    ],
)
def test_invalid_filters_are_rejected_with_a_clear_message(
    client: TestClient, params: dict[str, str], fragment: str
) -> None:
    response = client.get(f"{API}/kpis/summary", params=params)
    assert response.status_code == 422
    assert fragment in response.text


def test_invalid_endpoint_parameters_are_rejected(client: TestClient) -> None:
    cases = [
        ("/budget/variance", {"group_by": "galaxy"}),
        ("/profitability", {"group_by": "product", "category": "ZZZ"}),
        ("/records/monthly", {"page": 0}),
        ("/records/monthly", {"page_size": 5000}),
        ("/records/monthly", {"sort_by": "password"}),
        ("/exports/secrets", {}),
    ]
    for path, params in cases:
        assert client.get(f"{API}{path}", params=params).status_code == 422, path


def test_business_unit_codes_are_case_insensitive(client: TestClient) -> None:
    assert get(client, "/kpis/summary", business_unit="ret")["filters"]["business_units"] == ["RET"]


# --------------------------------------------------------------------------- #
# Time series
# --------------------------------------------------------------------------- #
def test_time_series_adds_up_to_the_kpis(client: TestClient) -> None:
    points = get(client, "/timeseries", **FY2025)["points"]
    summary = kpis(client, **FY2025)
    assert [p["month"] for p in points] == [f"2025-{m:02d}" for m in range(1, 13)]
    for field in ("net_revenue", "direct_costs", "operating_expenses", "operating_income"):
        assert sum(p[field] for p in points) == pytest.approx(
            summary[field]["value"], abs=12 * CENT
        )
        assert sum(p[f"budget_{field}"] for p in points) == pytest.approx(
            summary[field]["budget_value"], abs=12 * CENT
        )
    for point in points:
        assert point["gross_profit"] == pytest.approx(
            point["net_revenue"] - point["direct_costs"], abs=CENT
        )
        assert point["operating_margin"] == pytest.approx(
            point["operating_income"] / point["net_revenue"], abs=1e-6
        )


def test_growth_rates(client: TestClient, oracle: Oracle) -> None:
    points = {
        p["month"]: p for p in get(client, "/timeseries", start="2023-01", end="2025-12")["points"]
    }

    def revenue(month: str) -> float:
        return oracle.actual(month, month)["net_revenue"]

    assert points["2023-01"]["revenue_mom_pct"] is None  # first month of the history
    assert points["2023-12"]["revenue_yoy_pct"] is None  # no prior year yet
    assert points["2024-03"]["revenue_mom_pct"] == pytest.approx(
        revenue("2024-03") / revenue("2024-02") - 1, abs=1e-6
    )
    assert points["2025-06"]["revenue_yoy_pct"] == pytest.approx(
        revenue("2025-06") / revenue("2024-06") - 1, abs=1e-6
    )
    assert points["2023-03"]["revenue_rolling_3m"] == pytest.approx(
        (revenue("2023-01") + revenue("2023-02") + revenue("2023-03")) / 3, abs=CENT
    )
    assert points["2023-02"]["revenue_rolling_3m"] is None


def test_growth_of_the_first_visible_month_uses_history(client: TestClient) -> None:
    """Narrowing the period must not blank out growth that the data can support."""
    narrow = get(client, "/timeseries", start="2025-06", end="2025-08")["points"][0]
    wide = {p["month"]: p for p in get(client, "/timeseries", **FY2025)["points"]}["2025-06"]
    assert narrow["revenue_mom_pct"] is not None
    assert narrow == wide


def test_time_series_by_unit_matches_the_total(client: TestClient) -> None:
    series = get(client, "/timeseries/business-units", **FY2025)["series"]
    total = get(client, "/timeseries", **FY2025)["points"]
    assert {s["key"] for s in series} == {"RET", "ECM", "WHS", "COR"}
    for index, point in enumerate(total):
        assert sum(s["points"][index]["net_revenue"] for s in series) == pytest.approx(
            point["net_revenue"], abs=4 * CENT
        )
        assert sum(s["points"][index]["operating_income"] for s in series) == pytest.approx(
            point["operating_income"], abs=4 * CENT
        )


# --------------------------------------------------------------------------- #
# Budget versus actual
# --------------------------------------------------------------------------- #
def test_budget_statement_is_internally_consistent(client: TestClient) -> None:
    lines = {line["key"]: line for line in get(client, "/budget/statement", **FY2025)["lines"]}
    summary = kpis(client, **FY2025)
    accounts = [line for line in lines.values() if line["level"] == "account"]
    opex = [line for line in accounts if line["account_type"] == "OPERATING_EXPENSE"]

    assert len(accounts) == 13
    assert list(lines)[:3] == ["4000", "5000", "gross_profit"]
    assert list(lines)[-2:] == ["operating_expenses", "operating_income"]
    for column in ("actual", "budget", "variance"):
        assert lines["gross_profit"][column] == pytest.approx(
            lines["4000"][column] - lines["5000"][column], abs=2 * CENT
        )
        assert lines["operating_expenses"][column] == pytest.approx(
            sum(line[column] for line in opex), abs=11 * CENT
        )
        assert lines["operating_income"][column] == pytest.approx(
            lines["gross_profit"][column] - lines["operating_expenses"][column], abs=2 * CENT
        )
    assert lines["operating_income"]["actual"] == summary["operating_income"]["value"]
    assert lines["operating_income"]["budget"] == summary["operating_income"]["budget_value"]

    # The profit impacts of the account lines explain the operating income variance.
    assert sum(line["profit_impact"] for line in accounts) == pytest.approx(
        lines["operating_income"]["variance"], abs=13 * CENT
    )


def test_favorability_depends_on_the_kind_of_account(client: TestClient) -> None:
    lines = get(client, "/budget/statement", start="2024-04", end="2024-06", business_unit="WHS")
    by_key = {line["key"]: line for line in lines["lines"]}
    # Scenario S1: wholesale revenue fell short, so its volume-driven costs did too.
    assert by_key["4000"]["variance"] < 0
    assert by_key["4000"]["status"] == "unfavorable"
    assert by_key["4000"]["profit_impact"] < 0
    assert by_key["5000"]["variance"] < 0
    assert by_key["5000"]["status"] == "favorable"
    assert by_key["5000"]["profit_impact"] > 0


def test_budget_variance_by_month_and_unit(client: TestClient, oracle: Oracle) -> None:
    by_month = get(client, "/budget/variance", **FY2025, group_by="month")["rows"]
    by_unit = get(client, "/budget/variance", **FY2025, group_by="business_unit")["rows"]
    assert len(by_month) == 12
    assert [row["key"] for row in by_unit] == ["COR", "ECM", "RET", "WHS"]
    for measure in ("net_revenue", "direct_costs", "operating_expenses", "operating_income"):
        for field in ("actual", "budget", "variance"):
            assert sum(row[measure][field] for row in by_month) == pytest.approx(
                sum(row[measure][field] for row in by_unit), abs=16 * CENT
            )
    march = next(row for row in by_month if row["key"] == "2025-03")
    assert march["net_revenue"]["budget"] == pytest.approx(
        oracle.planned("2025-03", "2025-03")["net_revenue"], abs=CENT
    )
    for row in by_month:
        revenue = row["net_revenue"]
        assert revenue["variance"] == pytest.approx(revenue["actual"] - revenue["budget"], abs=CENT)


def test_budget_matrix_covers_every_unit_and_account(client: TestClient) -> None:
    cells = get(client, "/budget/matrix", **FY2025)["cells"]
    assert len(cells) == 4 * 13
    statement = {line["key"]: line for line in get(client, "/budget/statement", **FY2025)["lines"]}
    freight = [cell for cell in cells if cell["account_code"] == "6400"]
    assert sum(cell["actual"] for cell in freight) == pytest.approx(
        statement["6400"]["actual"], abs=4 * CENT
    )


# --------------------------------------------------------------------------- #
# Profitability and expenses
# --------------------------------------------------------------------------- #
def test_profitability_by_category_matches_the_oracle(client: TestClient, oracle: Oracle) -> None:
    body = get(client, "/profitability", **FY2025, group_by="category")
    sales = oracle.sales[
        (oracle.sales["month"] >= "2025-01") & (oracle.sales["month"] <= "2025-12")
    ]
    expected = sales.groupby("category_code")[
        ["net_sales_amount", "cogs_amount", "units_sold"]
    ].sum()
    assert len(body["rows"]) == 5
    for row in body["rows"]:
        truth = expected.loc[row["key"]]
        assert row["net_revenue"] == pytest.approx(truth["net_sales_amount"], abs=CENT)
        assert row["units"] == truth["units_sold"]
        assert row["gross_margin"] == pytest.approx(
            1 - truth["cogs_amount"] / truth["net_sales_amount"], abs=1e-6
        )
    assert sum(row["revenue_share"] for row in body["rows"]) == pytest.approx(1.0, abs=1e-5)
    assert sum(row["net_revenue"] for row in body["rows"]) == pytest.approx(
        body["total"]["net_revenue"], abs=5 * CENT
    )
    # Sorted by revenue, and operating figures are not available by category.
    revenues = [row["net_revenue"] for row in body["rows"]]
    assert revenues == sorted(revenues, reverse=True)
    assert all(row["operating_income"] is None for row in body["rows"])


def test_profitability_by_unit_includes_operating_income(client: TestClient) -> None:
    body = get(client, "/profitability", **FY2025, group_by="business_unit")
    summary = kpis(client, **FY2025)
    assert sum(row["operating_income"] for row in body["rows"]) == pytest.approx(
        summary["operating_income"]["value"], abs=4 * CENT
    )
    assert body["total"]["operating_income"] == pytest.approx(
        summary["operating_income"]["value"], abs=CENT
    )
    assert body["total"]["gross_margin"] == summary["gross_margin"]["value"]


def test_category_filter_restricts_products_and_hides_operating_income(
    client: TestClient,
) -> None:
    products = get(client, "/profitability", **FY2025, group_by="product", category="ele")
    assert len(products["rows"]) == 6
    assert {row["parent_key"] for row in products["rows"]} == {"ELE"}
    assert products["category"] == "ELE"

    by_unit = get(client, "/profitability", **FY2025, group_by="business_unit", category="ELE")
    assert all(row["operating_income"] is None for row in by_unit["rows"])
    assert by_unit["total"]["net_revenue"] == pytest.approx(
        products["total"]["net_revenue"], abs=CENT
    )


def test_expense_breakdowns_agree_on_the_total(client: TestClient) -> None:
    summary = kpis(client, **FY2025)
    totals = {}
    for group_by in ("account", "account_group", "cost_center", "cost_behavior"):
        body = get(client, "/expenses/breakdown", **FY2025, group_by=group_by)
        totals[group_by] = body["total"]["actual"]
        assert sum(row["actual"] for row in body["rows"]) == pytest.approx(
            body["total"]["actual"], abs=len(body["rows"]) * CENT
        )
        assert sum(row["share"] for row in body["rows"]) == pytest.approx(1.0, abs=1e-5)
    assert set(totals.values()) == {summary["operating_expenses"]["value"]}


def test_cost_center_breakdown_has_no_budget(client: TestClient) -> None:
    by_center = get(client, "/expenses/breakdown", **FY2025, group_by="cost_center")
    by_account = get(client, "/expenses/breakdown", **FY2025, group_by="account")
    assert len(by_center["rows"]) == 6
    assert all(row["budget"] is None and row["status"] is None for row in by_center["rows"])
    assert all(row["budget"] is not None for row in by_account["rows"])
    assert all(row["comparison"] is not None for row in by_center["rows"])


def test_expense_matrix_matches_the_breakdown(client: TestClient) -> None:
    matrix = get(client, "/expenses/matrix", **FY2025)
    total = get(client, "/expenses/breakdown", **FY2025)["total"]["actual"]
    assert sum(cell["amount"] for cell in matrix["cells"]) == pytest.approx(
        total, abs=len(matrix["cells"]) * CENT
    )
    assert len(matrix["cost_centers"]) == 6


# --------------------------------------------------------------------------- #
# Contribution analysis
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("basis", ["comparison", "budget"])
def test_bridge_adds_up(client: TestClient, basis: str) -> None:
    body = get(client, "/analysis/operating-income-bridge", **FY2025, basis=basis)
    steps = body["steps"]
    effects = [s["amount"] for s in steps if s["kind"] == "effect"]
    assert body["available"] is True
    assert steps[0]["kind"] == steps[-1]["kind"] == "total"
    assert steps[0]["amount"] + sum(effects) == pytest.approx(
        steps[-1]["amount"], abs=len(effects) * CENT
    )
    summary = kpis(client, **FY2025)["operating_income"]
    assert steps[-1]["amount"] == summary["value"]
    reference = summary["budget_value"] if basis == "budget" else summary["comparison_value"]
    assert steps[0]["amount"] == reference


def test_bridge_is_unavailable_without_a_comparison_period(client: TestClient) -> None:
    body = get(client, "/analysis/operating-income-bridge", start="2023-01", end="2023-12")
    assert body["available"] is False
    assert body["steps"] == []
    assert get(
        client, "/analysis/operating-income-bridge", start="2023-01", end="2023-12", basis="budget"
    )["available"]


@pytest.mark.parametrize("group_by", ["category", "business_unit"])
def test_price_volume_mix_explains_the_revenue_change(client: TestClient, group_by: str) -> None:
    body = get(client, "/analysis/price-volume-mix", **FY2025, group_by=group_by)
    revenue = kpis(client, **FY2025)["net_revenue"]
    total = body["total"]
    assert total["total_change"] == pytest.approx(revenue["change"], abs=2 * CENT)
    assert total["volume_effect"] + total["mix_effect"] + total["price_effect"] == pytest.approx(
        total["total_change"], abs=3 * CENT
    )
    for row in body["rows"]:
        assert row["volume_effect"] + row["mix_effect"] + row["price_effect"] == pytest.approx(
            row["total_change"], abs=3 * CENT
        )
    assert sum(row["total_change"] for row in body["rows"]) == pytest.approx(
        total["total_change"], abs=len(body["rows"]) * CENT
    )


def test_price_effect_reflects_the_documented_price_increases(client: TestClient) -> None:
    """List prices rose 3.5% in January 2025, so the price effect must be positive."""
    total = get(client, "/analysis/price-volume-mix", **FY2025)["total"]
    assert 0.02 < total["price_effect"] / total["base_revenue"] < 0.06


@pytest.mark.parametrize("group_by", ["category", "business_unit"])
def test_margin_drivers_explain_the_margin_change(client: TestClient, group_by: str) -> None:
    body = get(client, "/analysis/margin-drivers", **FY2025, group_by=group_by)
    margin = kpis(client, **FY2025)["gross_margin"]
    assert body["current_margin"] == margin["value"]
    assert body["margin_change"] == pytest.approx(margin["change"], abs=2e-6)
    assert body["rate_effect"] + body["mix_effect"] == pytest.approx(
        body["margin_change"], abs=3e-6
    )
    assert sum(row["total_effect"] for row in body["rows"]) == pytest.approx(
        body["margin_change"], abs=1e-5
    )


def test_margin_drivers_point_at_electronics_in_2025(client: TestClient) -> None:
    """Scenario S5 raised electronics supplier costs: the rate effect should show it."""
    rows = get(client, "/analysis/margin-drivers", **FY2025, group_by="category")["rows"]
    worst = min(rows, key=lambda row: row["rate_effect"])
    assert worst["key"] == "ELE"
    assert worst["rate_effect"] < -0.005


# --------------------------------------------------------------------------- #
# Anomalies and insights
# --------------------------------------------------------------------------- #
def test_anomalies_find_the_wholesale_revenue_drop(client: TestClient) -> None:
    body = get(client, "/analysis/anomalies", start="2024-01", end="2024-12", business_unit="WHS")
    revenue = [a for a in body["anomalies"] if a["account_code"] == "4000"]
    assert {"2024-04", "2024-05", "2024-06"} <= {a["month"] for a in revenue}
    for anomaly in revenue:
        assert anomaly["status"] == "unfavorable"
        assert anomaly["robust_z"] < -3.5
        assert anomaly["is_material"]
    assert body["method"]["z_threshold"] == 3.5
    assert body["method"]["series_evaluated"] == 13
    assert body["method"]["months_of_history"] == 36


def test_anomaly_scores_do_not_depend_on_the_selected_period(client: TestClient) -> None:
    wide = get(client, "/analysis/anomalies", start="2023-01", end="2025-12")["anomalies"]
    narrow = get(client, "/analysis/anomalies", start="2023-09", end="2023-09")["anomalies"]
    in_september = [a for a in wide if a["month"] == "2023-09"]
    assert narrow == in_september
    assert any(a["account_code"] == "6600" and a["business_unit_code"] == "RET" for a in narrow)


def test_immaterial_anomalies_are_optional(client: TestClient) -> None:
    period = {"start": "2023-01", "end": "2025-12"}
    material = get(client, "/analysis/anomalies", **period)["anomalies"]
    everything = get(client, "/analysis/anomalies", **period, include_immaterial=True)["anomalies"]
    assert all(a["is_material"] for a in material)
    assert len(everything) > len(material)
    assert [a for a in everything if a["is_material"]] == material
    for anomaly in everything:
        assert abs(anomaly["robust_z"]) > 3.5
        assert (abs(anomaly["variance"]) >= anomaly["materiality_threshold"]) == anomaly[
            "is_material"
        ]


def test_insights_are_computed_from_the_filtered_data(client: TestClient, oracle: Oracle) -> None:
    body = get(client, "/insights", **FY2025)
    insights = {insight["id"]: insight for insight in body["insights"]}
    assert {
        "operating_income",
        "revenue_vs_budget",
        "operating_income_vs_budget",
        "top_business_unit",
        "category_margins",
        "gross_margin_drivers",
        "revenue_price_volume_mix",
        "anomalies",
        "monthly_pattern",
    } <= set(insights)

    current, planned = oracle.actual("2025-01", "2025-12"), oracle.planned("2025-01", "2025-12")
    evidence = {e["label"]: e["value"] for e in insights["revenue_vs_budget"]["evidence"]}
    assert evidence["Actual"] == pytest.approx(current["net_revenue"], abs=CENT)
    assert evidence["Budget"] == pytest.approx(planned["net_revenue"], abs=CENT)
    assert evidence["Variance"] == pytest.approx(
        current["net_revenue"] - planned["net_revenue"], abs=2 * CENT
    )
    for insight in insights.values():
        assert insight["title"]
        assert insight["detail"]
        assert insight["evidence"]
        assert insight["tone"] in {"positive", "negative", "neutral"}


def test_insights_adapt_to_a_single_unit_and_to_missing_history(client: TestClient) -> None:
    single = {i["id"] for i in get(client, "/insights", **FY2025, business_unit="ECM")["insights"]}
    assert "top_business_unit" not in single  # nothing to rank

    first_year = get(client, "/insights", start="2023-01", end="2023-12")["insights"]
    ids = {insight["id"] for insight in first_year}
    assert "gross_margin_drivers" not in ids
    assert "revenue_price_volume_mix" not in ids
    headline = next(insight for insight in first_year if insight["id"] == "operating_income")
    assert "No prior year data" in headline["detail"]

    one_month = {
        i["id"] for i in get(client, "/insights", start="2025-05", end="2025-05")["insights"]
    }
    assert "monthly_pattern" not in one_month


# --------------------------------------------------------------------------- #
# Analytical table, exports and data quality
# --------------------------------------------------------------------------- #
def test_monthly_records_pagination(client: TestClient) -> None:
    first = get(client, "/records/monthly", **FY2025, page=1, page_size=10)
    last = get(client, "/records/monthly", **FY2025, page=5, page_size=10)
    beyond = get(client, "/records/monthly", **FY2025, page=9, page_size=10)
    assert first["pagination"] == {"page": 1, "page_size": 10, "total_items": 48, "total_pages": 5}
    assert (len(first["rows"]), len(last["rows"]), len(beyond["rows"])) == (10, 8, 0)

    everything = get(client, "/records/monthly", **FY2025, page_size=200)["rows"]
    keys = [(row["month"], row["business_unit_code"]) for row in everything]
    assert len(set(keys)) == 48
    assert sum(row["net_revenue"] for row in everything) == pytest.approx(
        kpis(client, **FY2025)["net_revenue"]["value"], abs=48 * CENT
    )


def test_monthly_records_filter_by_budget_attainment(client: TestClient) -> None:
    everything = get(client, "/records/monthly", **FY2025, page_size=200)
    above = get(client, "/records/monthly", **FY2025, page_size=200, revenue_vs_budget="above")
    below = get(client, "/records/monthly", **FY2025, page_size=200, revenue_vs_budget="below")
    assert above["revenue_vs_budget"] == "above"
    assert all(row["revenue_variance_pct"] > 0 for row in above["rows"])
    assert all(row["revenue_variance_pct"] < 0 for row in below["rows"])
    assert (
        above["pagination"]["total_items"] + below["pagination"]["total_items"]
        == (everything["pagination"]["total_items"])
    )
    assert above["rows"]
    assert below["rows"]
    assert (
        client.get(f"{API}/records/monthly", params={"revenue_vs_budget": "x"}).status_code == 422
    )


@pytest.mark.parametrize(
    ("sort_by", "sort_dir"),
    [("net_revenue", "desc"), ("operating_margin", "asc"), ("month", "asc")],
)
def test_monthly_records_sorting(client: TestClient, sort_by: str, sort_dir: str) -> None:
    rows = get(
        client, "/records/monthly", **FY2025, page_size=200, sort_by=sort_by, sort_dir=sort_dir
    )["rows"]
    values = [row[sort_by] for row in rows]
    assert values == sorted(values, reverse=sort_dir == "desc")


@pytest.mark.parametrize(
    "export_name",
    [
        "monthly-pnl",
        "budget-by-account",
        "sales-by-product",
        "expenses-by-cost-center",
        "anomalies",
    ],
)
def test_csv_exports_are_well_formed(client: TestClient, export_name: str) -> None:
    response = client.get(f"{API}/exports/{export_name}", params={**FY2025, "business_unit": "RET"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert (
        response.headers["content-disposition"]
        == f'attachment; filename="{export_name}_2025-01_2025-12_RET.csv"'
    )
    frame = pd.read_csv(io.StringIO(response.text))
    assert not frame.empty
    assert set(frame["business_unit_code"]) == {"RET"}


def test_csv_export_matches_the_api_figures(client: TestClient) -> None:
    response = client.get(f"{API}/exports/monthly-pnl", params=FY2025)
    frame = pd.read_csv(io.StringIO(response.text))
    summary = kpis(client, **FY2025)
    assert len(frame) == 48
    assert frame["net_revenue"].sum() == pytest.approx(summary["net_revenue"]["value"], abs=1)
    assert frame["operating_income"].sum() == pytest.approx(
        summary["operating_income"]["value"], abs=1
    )
    detail = pd.read_csv(
        io.StringIO(client.get(f"{API}/exports/budget-by-account", params=FY2025).text)
    )
    assert len(detail) == 12 * 4 * 13
    assert detail["profit_impact"].sum() == pytest.approx(
        summary["operating_income"]["budget_variance"], abs=1
    )


def test_data_quality_report(client: TestClient) -> None:
    body = get(client, "/data-quality")
    summary = body["summary"]
    assert body["latest_run"]["status"] in {"SUCCESS", "FAILED"}
    assert summary["total_checks"] == len(body["checks"])
    assert summary["passed"] + summary["warnings"] + summary["failed"] == summary["total_checks"]
    assert body["table_row_counts"]["fact_sales"] == 109_759
    assert body["table_row_counts"]["dim_date"] == 1096
    assert len(body["recent_runs"]) >= 1
    for load in body["table_loads"]:
        assert load["rows_read"] == (
            load["rows_rejected"] + load["rows_deduplicated"] + load["rows_loaded"]
        )


# --------------------------------------------------------------------------- #
# Failure modes
# --------------------------------------------------------------------------- #
def test_empty_warehouse_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(warehouse, "available_period", lambda session: None)
    response = client.get(f"{API}/kpis/summary")
    assert response.status_code == 503
    assert "Run the ETL pipeline" in response.json()["detail"]
    assert client.get(f"{API}/dimensions").status_code == 503
    health = client.get(f"{API}/health").json()
    assert health["data"]["loaded"] is False


def test_only_get_is_allowed(client: TestClient) -> None:
    assert client.post(f"{API}/kpis/summary").status_code == 405
    assert client.delete(f"{API}/records/monthly").status_code == 405
