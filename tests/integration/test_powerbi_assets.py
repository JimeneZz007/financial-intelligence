"""The values published for checking the Power BI measures must match the warehouse."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
POWERBI = REPO_ROOT / "powerbi"


@pytest.fixture(scope="module")
def exporter() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "export_powerbi_assets", REPO_ROOT / "scripts" / "export_powerbi_assets.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def computed(exporter: ModuleType, loaded_engine: Engine) -> list[tuple[str, str, str, str]]:
    with loaded_engine.connect() as connection:
        sales, expenses, budget = (
            pd.read_sql(text(sql), connection)
            for sql in (exporter.SALES_SQL, exporter.EXPENSES_SQL, exporter.BUDGET_SQL)
        )
    measures = ["units", "gross", "discounts", "revenue", "cogs"]
    sales[measures] = sales[measures].astype(float)
    expenses["amount"] = expenses["amount"].astype(float)
    budget["amount"] = budget["amount"].astype(float)
    return exporter.expected_values(sales, expenses, budget)


def test_published_expected_values_match_a_fresh_calculation(
    computed: list[tuple[str, str, str, str]],
) -> None:
    with (POWERBI / "validation" / "expected_values.csv").open(encoding="utf-8") as handle:
        published = [tuple(row) for row in csv.reader(handle)][1:]
    assert published == computed


def test_expected_values_agree_with_the_api(
    computed: list[tuple[str, str, str, str]], client: TestClient
) -> None:
    """Three calculations of the same figures: SQL here, the API, and DAX in the report."""
    expected = {
        measure: value
        for slicers, context, measure, value in computed
        if slicers == "Year = 2025" and context == "Card"
    }
    response = client.get("/api/v1/kpis/summary", params={"start": "2025-01", "end": "2025-12"})
    kpis = {kpi["id"]: kpi for kpi in response.json()["kpis"]}

    assert float(expected["Net Revenue"]) == pytest.approx(kpis["net_revenue"]["value"], abs=0.01)
    assert float(expected["Operating Income"]) == pytest.approx(
        kpis["operating_income"]["value"], abs=0.01
    )
    assert float(expected["Budget Operating Income"]) == pytest.approx(
        kpis["operating_income"]["budget_value"], abs=0.01
    )
    assert float(expected["Gross Margin %"].rstrip("%")) / 100 == pytest.approx(
        kpis["gross_margin"]["value"], abs=1e-6
    )


def test_profit_impact_total_equals_the_operating_income_variance(
    computed: list[tuple[str, str, str, str]],
) -> None:
    by_key = {(slicers, context, measure): value for slicers, context, measure, value in computed}
    total = float(by_key[("Year = 2025", "Matrix grand total (accounts on rows)", "Profit Impact")])
    variance = float(by_key[("Year = 2025", "Card", "Operating Income Variance")])
    assert total == pytest.approx(variance, abs=0.01)


def test_theme_is_valid_json_with_the_product_palette() -> None:
    theme = json.loads((POWERBI / "theme" / "financial-intelligence.json").read_text("utf-8"))
    assert theme["good"] == "#12a594"
    assert theme["bad"] == "#e5604d"
    assert theme["dataColors"][:4] == ["#3987e5", "#c98500", "#d55181", "#9085e9"]


def test_every_dax_measure_with_an_expected_value_is_defined(
    computed: list[tuple[str, str, str, str]],
) -> None:
    dax = (POWERBI / "measures" / "measures.dax").read_text("utf-8")
    defined = {
        line.split("=", 1)[0].strip()
        for line in dax.splitlines()
        if "=" in line and not line.startswith(("//", " ", "\t", "VAR", "RETURN"))
    }
    used = {measure for _, _, measure, _ in computed}
    assert used - defined == set()
