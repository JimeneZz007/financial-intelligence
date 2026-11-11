"""The synthetic generator must be reproducible and financially coherent."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pipelines.generate import config as cfg
from pipelines.generate import defects
from pipelines.generate.dataset import MANIFEST_NAME, Dataset, build_dataset, write_dataset
from pipelines.generate.expenses import allocate_cents
from pipelines.generate.scenarios import SCENARIOS, month_range


def _monthly(frame: pd.DataFrame, date_column: str, value: str) -> pd.Series:
    return frame.groupby([frame[date_column].str.slice(0, 7), "business_unit_code"])[value].sum()


# --------------------------------------------------------------------------- #
# Reproducibility
# --------------------------------------------------------------------------- #
def test_same_seed_produces_identical_files(tmp_path: Path, dataset: Dataset) -> None:
    first = write_dataset(dataset, tmp_path / "a")
    second = write_dataset(build_dataset(), tmp_path / "b")
    assert first["files"] == second["files"]


def test_different_seed_changes_the_data(dataset: Dataset) -> None:
    other = build_dataset(seed=cfg.SEED + 1)
    assert (
        other.control_totals["sales_transactions"]["net_sales_amount"]
        != dataset.control_totals["sales_transactions"]["net_sales_amount"]
    )


def test_committed_manifest_matches_regenerated_data(
    tmp_path: Path, dataset: Dataset, repo_root: Path
) -> None:
    """The manifest under version control is the reference for reproducibility."""
    committed = json.loads((repo_root / "data" / "synthetic" / MANIFEST_NAME).read_text())
    regenerated = write_dataset(dataset, tmp_path)
    assert regenerated["files"] == committed["files"]
    assert regenerated["control_totals"] == committed["control_totals"]


# --------------------------------------------------------------------------- #
# Structure and grain
# --------------------------------------------------------------------------- #
def test_sales_grain_is_unique(dataset: Dataset) -> None:
    sales = dataset.clean["sales_transactions"]
    key = ["transaction_date", "business_unit_code", "product_code"]
    assert not sales.duplicated(key).any()


def test_period_is_fully_covered(dataset: Dataset) -> None:
    sales = dataset.clean["sales_transactions"]
    assert sales["transaction_date"].min() == cfg.PERIOD_START.isoformat()
    assert sales["transaction_date"].max() == cfg.PERIOD_END.isoformat()
    months = sales["transaction_date"].str.slice(0, 7).nunique()
    assert months == 36


def test_budget_is_a_complete_grid(dataset: Dataset) -> None:
    budget = dataset.clean["budget_plan"]
    key = ["fiscal_year", "fiscal_month", "business_unit_code", "account_code"]
    assert not budget.duplicated(key).any()
    assert len(budget) == 36 * len(cfg.BUSINESS_UNITS) * len(cfg.ACCOUNTS)
    assert (budget["budget_amount"] > 0).all()
    assert (budget["budget_amount"] % cfg.BUDGET_ROUNDING == 0).all()


def test_expense_entries_reference_valid_master_data(dataset: Dataset) -> None:
    ledger = dataset.clean["expense_ledger"]
    assert ledger["entry_id"].is_unique
    assert set(ledger["account_code"]) == set(cfg.OPEX_ACCOUNT_CODES)
    assert set(ledger["cost_center_code"]) <= {cc.code for cc in cfg.COST_CENTERS}
    assert (ledger["amount"] > 0).all()


def test_master_data_shares_are_consistent() -> None:
    for bu in cfg.BUSINESS_UNITS:
        assert sum(bu.category_mix.values()) == pytest.approx(1.0)
    for category in cfg.CATEGORIES:
        weights = [p.category_weight for p in cfg.PRODUCTS if p.category_code == category.code]
        assert sum(weights) == pytest.approx(1.0)
    for account_code in cfg.OPEX_ACCOUNT_CODES:
        for bu_code in cfg.BU_CODES:
            assert sum(cfg.cost_center_split(account_code, bu_code).values()) == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# Financial coherence
# --------------------------------------------------------------------------- #
def test_sales_amount_identities_hold_to_the_cent(dataset: Dataset) -> None:
    sales = dataset.clean["sales_transactions"]
    cents = (sales[["gross_sales_amount", "discount_amount", "net_sales_amount"]] * 100).round()
    assert (
        cents["net_sales_amount"] == cents["gross_sales_amount"] - cents["discount_amount"]
    ).all()
    assert (sales["units_sold"] > 0).all()
    assert (sales["discount_amount"] >= 0).all()
    assert (sales["discount_amount"] < sales["gross_sales_amount"]).all()


def test_no_impossible_margins(dataset: Dataset) -> None:
    """Every product is sold above cost on average and margins stay in a plausible band."""
    sales = dataset.clean["sales_transactions"]
    by_product = sales.groupby("product_code")[["net_sales_amount", "cogs_amount"]].sum()
    margin = 1 - by_product["cogs_amount"] / by_product["net_sales_amount"]
    assert margin.between(0.05, 0.70).all()


def test_operating_result_is_plausible_for_every_unit_and_year(dataset: Dataset) -> None:
    sales = dataset.clean["sales_transactions"]
    ledger = dataset.clean["expense_ledger"]
    keys = lambda frame, col: [frame[col].str.slice(0, 4), frame["business_unit_code"]]  # noqa: E731
    revenue = sales.groupby(keys(sales, "transaction_date"))["net_sales_amount"].sum()
    cogs = sales.groupby(keys(sales, "transaction_date"))["cogs_amount"].sum()
    opex = ledger.groupby(keys(ledger, "posting_date"))["amount"].sum()
    operating_margin = (revenue - cogs - opex) / revenue
    assert operating_margin.between(0.0, 0.20).all()


def test_revenue_seasonality_peaks_in_the_fourth_quarter(dataset: Dataset) -> None:
    sales = dataset.clean["sales_transactions"]
    retail = sales[sales["business_unit_code"] == "RET"]
    by_month = retail.groupby(retail["transaction_date"].str.slice(5, 7))["net_sales_amount"].sum()
    assert by_month.idxmax() in {"11", "12"}
    assert by_month.idxmin() in {"01", "02"}


def test_ecommerce_grows_faster_than_retail(dataset: Dataset) -> None:
    sales = dataset.clean["sales_transactions"]
    yearly = (
        sales.groupby([sales["transaction_date"].str.slice(0, 4), "business_unit_code"])[
            "net_sales_amount"
        ]
        .sum()
        .unstack()
    )
    growth = yearly.loc["2025"] / yearly.loc["2023"] - 1
    assert growth["ECM"] > growth["RET"] + 0.20


# --------------------------------------------------------------------------- #
# Scenarios leave their documented footprint
# --------------------------------------------------------------------------- #
def _revenue_vs_budget(dataset: Dataset) -> pd.Series:
    actual = _monthly(dataset.clean["sales_transactions"], "transaction_date", "net_sales_amount")
    budget = dataset.clean["budget_plan"]
    budget = budget[budget["account_code"] == cfg.REVENUE_ACCOUNT]
    month_key = (
        budget["fiscal_year"].astype(str) + "-" + budget["fiscal_month"].astype(str).str.zfill(2)
    )
    planned = budget.groupby([month_key, "business_unit_code"])["budget_amount"].sum()
    return actual / planned - 1


def test_scenario_s1_wholesale_revenue_falls_below_budget(dataset: Dataset) -> None:
    variance = _revenue_vs_budget(dataset)
    for month in month_range("2024-04", "2024-06"):
        assert variance[(month, "WHS")] < -0.20
    assert variance[("2024-03", "WHS")] > -0.10


def test_scenario_s4_corporate_revenue_exceeds_budget(dataset: Dataset) -> None:
    variance = _revenue_vs_budget(dataset)
    for month in month_range("2025-07", "2025-12"):
        assert variance[(month, "COR")] > 0.15


def test_scenario_s7_legal_settlement_is_in_the_ledger(dataset: Dataset) -> None:
    ledger = dataset.clean["expense_ledger"]
    services = ledger[(ledger["account_code"] == "6600") & (ledger["business_unit_code"] == "RET")]
    by_month = services.groupby(services["posting_date"].str.slice(0, 7))["amount"].sum()
    assert by_month["2023-09"] > 185_000
    assert by_month.drop("2023-09").max() < 30_000


def test_scenario_s5_compresses_electronics_margin(dataset: Dataset) -> None:
    sales = dataset.clean["sales_transactions"]
    electronics = sales[sales["product_code"].str.startswith("ELE")]
    half = electronics["transaction_date"].map(
        lambda d: "2025H1" if "2025-01" <= d[:7] <= "2025-06" else d[:4]
    )
    totals = electronics.groupby(half)[["net_sales_amount", "cogs_amount"]].sum()
    margin = 1 - totals["cogs_amount"] / totals["net_sales_amount"]
    assert margin["2024"] - margin["2025H1"] > 0.03


def test_every_scenario_declares_a_primary_signature() -> None:
    for scenario in SCENARIOS:
        assert any(s.role == "PRIMARY" for s in scenario.signatures), scenario.id


# --------------------------------------------------------------------------- #
# Injected defects and helpers
# --------------------------------------------------------------------------- #
def test_raw_extracts_contain_exactly_the_documented_extra_rows(dataset: Dataset) -> None:
    extra_sales = sum(v for k, v in defects.SALES_DEFECTS.items() if k != "CODE_FORMAT")
    extra_expenses = sum(v for k, v in defects.EXPENSE_DEFECTS.items() if k != "DATE_FORMAT")
    assert len(dataset.raw["sales_transactions"]) == (
        len(dataset.clean["sales_transactions"]) + extra_sales
    )
    assert len(dataset.raw["expense_ledger"]) == (
        len(dataset.clean["expense_ledger"]) + extra_expenses
    )
    assert len(dataset.raw["budget_plan"]) == (
        len(dataset.clean["budget_plan"]) + defects.BUDGET_DEFECTS["DUPLICATE_ROW"]
    )


@pytest.mark.parametrize("total", [0, 1, 99, 100, 123_456_789])
def test_allocate_cents_preserves_the_total(total: int) -> None:
    parts = allocate_cents(total, np.array([0.55, 0.06, 0.16, 0.12, 0.05, 0.06]))
    assert parts.sum() == total
    assert (parts >= 0).all()
