"""Transform step: standardisation, row rules, deduplication and typing (no database)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from pipelines.etl import quality as dq
from pipelines.etl.transform import (
    build_dim_date,
    clean_budget,
    clean_expenses,
    clean_master_data,
    clean_sales,
)
from pipelines.generate import defects
from pipelines.generate.dataset import Dataset


@pytest.fixture(scope="module")
def master(dataset: Dataset) -> dict[str, pd.DataFrame]:
    cleaned, checks = clean_master_data(dataset.raw)
    assert all(check.status == dq.PASS for check in checks)
    return cleaned


def _sales_row(**overrides: str) -> dict[str, str]:
    row = {
        "transaction_date": "2024-03-15",
        "business_unit_code": "RET",
        "product_code": "ELE-001",
        "units_sold": "2",
        "gross_sales_amount": "1798.00",
        "discount_amount": "98.00",
        "net_sales_amount": "1700.00",
        "cogs_amount": "1300.00",
    }
    return row | overrides


def _reasons(rejected: pd.DataFrame) -> list[str]:
    return sorted(rejected["reject_reason"])


# --------------------------------------------------------------------------- #
# The ETL recovers exactly the clean dataset from the defective extracts
# --------------------------------------------------------------------------- #
def test_sales_cleaning_recovers_the_clean_dataset(dataset: Dataset, master: dict) -> None:
    result = clean_sales(dataset.raw["sales_transactions"], master)
    expected = dataset.clean["sales_transactions"]
    key = ["transaction_date", "business_unit_code", "product_code"]

    recovered = result.valid.assign(
        transaction_date=result.valid["transaction_date"].dt.strftime("%Y-%m-%d")
    )
    pd.testing.assert_frame_equal(
        recovered.sort_values(key).reset_index(drop=True),
        expected.sort_values(key).reset_index(drop=True),
        check_dtype=False,
    )
    assert result.rows_standardized == defects.SALES_DEFECTS["CODE_FORMAT"]
    assert result.rows_deduplicated == defects.SALES_DEFECTS["DUPLICATE_ROW"]
    assert result.rejected["reject_reason"].value_counts().to_dict() == {
        "SALES_KNOWN_PRODUCT": defects.SALES_DEFECTS["UNKNOWN_PRODUCT"],
        "SALES_REQUIRED_FIELDS": defects.SALES_DEFECTS["MISSING_UNITS"],
        "SALES_NET_IDENTITY": defects.SALES_DEFECTS["AMOUNT_MISMATCH"],
    }


def test_expense_cleaning_recovers_the_clean_dataset(dataset: Dataset, master: dict) -> None:
    result = clean_expenses(dataset.raw["expense_ledger"], master)
    expected = dataset.clean["expense_ledger"]

    recovered = result.valid.assign(
        posting_date=result.valid["posting_date"].dt.strftime("%Y-%m-%d")
    )
    pd.testing.assert_frame_equal(
        recovered.sort_values("entry_id").reset_index(drop=True),
        expected.sort_values("entry_id").reset_index(drop=True),
        check_dtype=False,
    )
    assert result.rows_standardized == defects.EXPENSE_DEFECTS["DATE_FORMAT"]
    assert result.rows_deduplicated == defects.EXPENSE_DEFECTS["DUPLICATE_ROW"]
    assert result.rejected["reject_reason"].value_counts().to_dict() == {
        "EXPENSES_POSITIVE_AMOUNT": defects.EXPENSE_DEFECTS["NON_POSITIVE_AMOUNT"],
        "EXPENSES_KNOWN_COST_CENTER": defects.EXPENSE_DEFECTS["UNKNOWN_COST_CENTER"],
    }


def test_budget_cleaning_recovers_the_clean_dataset(dataset: Dataset, master: dict) -> None:
    result = clean_budget(dataset.raw["budget_plan"], master)
    assert len(result.valid) == len(dataset.clean["budget_plan"])
    assert result.rows_deduplicated == defects.BUDGET_DEFECTS["DUPLICATE_ROW"]
    assert result.rejected.empty
    assert result.valid["budget_amount"].sum() == pytest.approx(
        dataset.clean["budget_plan"]["budget_amount"].sum()
    )
    assert not any(check.is_blocking_failure for check in result.checks)


def test_row_accounting_always_balances(dataset: Dataset, master: dict) -> None:
    for result in (
        clean_sales(dataset.raw["sales_transactions"], master),
        clean_expenses(dataset.raw["expense_ledger"], master),
        clean_budget(dataset.raw["budget_plan"], master),
    ):
        assert result.rows_read == (
            len(result.valid) + len(result.rejected) + result.rows_deduplicated
        )


# --------------------------------------------------------------------------- #
# Individual rules on hand-written rows
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("overrides", "expected_reason"),
    [
        ({"units_sold": ""}, "SALES_REQUIRED_FIELDS"),
        ({"transaction_date": "2024-02-30"}, "SALES_VALID_DATE"),
        ({"transaction_date": "not a date"}, "SALES_VALID_DATE"),
        ({"units_sold": "0"}, "SALES_VALID_AMOUNTS"),
        ({"units_sold": "1.5"}, "SALES_VALID_AMOUNTS"),
        ({"cogs_amount": "-1.00"}, "SALES_VALID_AMOUNTS"),
        ({"gross_sales_amount": "abc"}, "SALES_VALID_AMOUNTS"),
        ({"business_unit_code": "XXX"}, "SALES_KNOWN_BUSINESS_UNIT"),
        ({"product_code": "ELE-999"}, "SALES_KNOWN_PRODUCT"),
        ({"net_sales_amount": "1700.01"}, "SALES_NET_IDENTITY"),
    ],
)
def test_sales_rules_quarantine_invalid_rows(
    master: dict, overrides: dict[str, str], expected_reason: str
) -> None:
    raw = pd.DataFrame([_sales_row(), _sales_row(product_code="ELE-002") | overrides])
    result = clean_sales(raw, master)
    assert len(result.valid) == 1
    assert _reasons(result.rejected) == [expected_reason]


def test_recoverable_format_defects_are_repaired_not_rejected(master: dict) -> None:
    raw = pd.DataFrame([_sales_row(business_unit_code=" ret ", product_code="ele-001")])
    result = clean_sales(raw, master)
    assert result.rejected.empty
    assert result.rows_standardized == 1
    assert result.valid.iloc[0]["business_unit_code"] == "RET"
    assert result.valid.iloc[0]["product_code"] == "ELE-001"


def test_alternate_date_format_is_converted(master: dict) -> None:
    raw = pd.DataFrame(
        [
            {
                "entry_id": "EXP-0000001",
                "posting_date": "15/03/2024",
                "business_unit_code": "RET",
                "cost_center_code": "SAL",
                "account_code": "6100",
                "amount": "100.00",
            }
        ]
    )
    result = clean_expenses(raw, master)
    assert result.rejected.empty
    assert result.valid.iloc[0]["posting_date"] == pd.Timestamp("2024-03-15")


def test_expenses_cannot_be_posted_to_revenue_or_cogs_accounts(master: dict) -> None:
    """Prevents double counting: COGS lives only in the sales fact."""
    raw = pd.DataFrame(
        [
            {
                "entry_id": f"EXP-000000{i}",
                "posting_date": "2024-03-15",
                "business_unit_code": "RET",
                "cost_center_code": "SAL",
                "account_code": account,
                "amount": "100.00",
            }
            for i, account in enumerate(["6100", "5000", "4000"])
        ]
    )
    result = clean_expenses(raw, master)
    assert list(result.valid["account_code"]) == ["6100"]
    assert _reasons(result.rejected) == ["EXPENSES_OPERATING_ACCOUNT"] * 2


def test_conflicting_rows_for_the_same_key_block_the_run(master: dict) -> None:
    """Two different rows for one grain key cannot be resolved automatically."""
    raw = pd.DataFrame(
        [
            _sales_row(),
            _sales_row(units_sold="3", gross_sales_amount="2697.00", net_sales_amount="2599.00"),
        ]
    )
    result = clean_sales(raw, master)
    grain = next(check for check in result.checks if check.code == "SALES_GRAIN_UNIQUE")
    assert grain.status == dq.FAIL
    with pytest.raises(dq.DataQualityError):
        dq.raise_on_blocking(result.checks)


def test_reject_rate_above_tolerance_blocks_the_run(master: dict) -> None:
    raw = pd.DataFrame([_sales_row(), _sales_row(product_code="ELE-999")])
    result = clean_sales(raw, master)
    rate = next(check for check in result.checks if check.code.endswith("_REJECT_RATE"))
    assert rate.status == dq.FAIL
    assert rate.is_blocking_failure


def test_incomplete_budget_grid_is_detected(dataset: Dataset, master: dict) -> None:
    raw = dataset.raw["budget_plan"].iloc[5:]
    result = clean_budget(raw, master)
    grid = next(check for check in result.checks if check.code == "BUDGET_GRID_COMPLETE")
    assert grid.status == dq.FAIL
    assert grid.rows_failed >= 1


def test_master_data_detects_category_with_two_names(dataset: Dataset) -> None:
    frames = {name: frame.copy() for name, frame in dataset.raw.items()}
    frames["products"].loc[0, "category_name"] = "Gadgets"
    _, checks = clean_master_data(frames)
    dependency = next(c for c in checks if c.code == "MASTER_CATEGORY_NAME_DEPENDENCY")
    assert dependency.status == dq.FAIL


# --------------------------------------------------------------------------- #
# Date dimension
# --------------------------------------------------------------------------- #
def test_dim_date_covers_whole_months_without_gaps() -> None:
    dim = build_dim_date(date(2024, 1, 15), date(2024, 3, 10))
    assert dim["full_date"].iloc[0] == date(2024, 1, 1)
    assert dim["full_date"].iloc[-1] == date(2024, 3, 31)
    assert len(dim) == 31 + 29 + 31  # 2024 is a leap year
    assert dim["date_key"].is_unique


def test_dim_date_attributes() -> None:
    dim = build_dim_date(date(2024, 3, 1), date(2024, 3, 31)).set_index("date_key")
    saturday = dim.loc[20240316]
    assert saturday["day_name"] == "Saturday"
    assert saturday["day_of_week"] == 6
    assert bool(saturday["is_weekend"])
    assert saturday["quarter_label"] == "2024-Q1"
    assert saturday["year_month"] == "2024-03"
    assert saturday["month_start_key"] == 20240301
    assert int(dim["is_month_start"].sum()) == 1
