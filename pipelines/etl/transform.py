"""Transform: standardise, validate, deduplicate and type the source extracts.

Each fact extract goes through the same four steps:

1. **Standardise** recoverable format problems (whitespace, casing, alternate date format).
2. **Validate** row by row; rows breaking a rule are quarantined with the rule code.
3. **Deduplicate** exact duplicates.
4. **Assert the grain**: the business key must be unique, otherwise the run aborts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from pipelines.etl import quality as dq
from pipelines.etl.quality import CheckResult, RowRule

SALES, EXPENSES, BUDGET, MASTER = (
    "sales_transactions",
    "expense_ledger",
    "budget_plan",
    "master_data",
)

OPERATING_EXPENSE = "OPERATING_EXPENSE"
ACCOUNT_TYPES = {"REVENUE", "DIRECT_COST", OPERATING_EXPENSE}

_ISO_DATE = "%Y-%m-%d"
_ALTERNATE_DATE = r"^(\d{2})/(\d{2})/(\d{4})$"  # DD/MM/YYYY


@dataclass(frozen=True)
class CleanExtract:
    name: str
    valid: pd.DataFrame  # typed, deduplicated rows ready to be keyed and loaded
    rejected: pd.DataFrame  # quarantined rows (as text) with a reject_reason column
    rows_read: int
    rows_standardized: int
    rows_deduplicated: int
    checks: list[CheckResult]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _standardise(
    frame: pd.DataFrame, code_columns: list[str], date_column: str | None = None
) -> tuple[pd.DataFrame, int]:
    """Trim every cell, upper-case code columns and normalise DD/MM/YYYY dates."""
    out = frame.apply(lambda column: column.str.strip())
    for column in code_columns:
        out[column] = out[column].str.upper()
    if date_column is not None:
        out[date_column] = out[date_column].str.replace(_ALTERNATE_DATE, r"\3-\2-\1", regex=True)
    changed = int((out != frame).any(axis=1).sum())
    return out, changed


def _any_blank(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    return (frame[columns] == "").any(axis=1)


def _not_a_date(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, format=_ISO_DATE, errors="coerce").isna()


def _number(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce")


def _not_a_positive_integer(values: pd.Series) -> pd.Series:
    numbers = _number(values)
    return numbers.isna() | (numbers <= 0) | (numbers % 1 != 0)


def _negative_or_not_numeric(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    numbers = frame[columns].apply(_number)
    return numbers.isna().any(axis=1) | (numbers < 0).any(axis=1)


def _finish(
    name: str,
    prefix: str,
    raw: pd.DataFrame,
    standardised: pd.DataFrame,
    rows_standardized: int,
    rules: list[RowRule],
    key: list[str],
    standardise_label: str,
) -> tuple[pd.DataFrame, pd.DataFrame, int, list[CheckResult]]:
    """Steps 2-4 shared by every fact extract. Returns (valid, rejected, n_duplicates, checks)."""
    checks = [
        dq.informational(
            code=f"{prefix}_STANDARDISED",
            name=standardise_label,
            dataset=name,
            quality_dimension="consistency",
            rows_checked=len(raw),
            rows_affected=rows_standardized,
        )
    ]
    valid, rejected, rule_checks = dq.apply_row_rules(standardised, rules, name)
    checks += rule_checks

    deduplicated = valid.drop_duplicates()
    duplicates = len(valid) - len(deduplicated)
    checks.append(
        dq.informational(
            code=f"{prefix}_EXACT_DUPLICATES",
            name="Exact duplicate rows are removed",
            dataset=name,
            quality_dimension="uniqueness",
            rows_checked=len(valid),
            rows_affected=duplicates,
        )
    )
    checks.append(
        dq.dataset_check(
            code=f"{prefix}_GRAIN_UNIQUE",
            name=f"Business key is unique after cleaning ({', '.join(key)})",
            dataset=name,
            quality_dimension="uniqueness",
            stage=dq.SOURCE,
            rows_checked=len(deduplicated),
            rows_failed=int(deduplicated.duplicated(key, keep=False).sum()),
        )
    )
    return deduplicated, rejected, duplicates, checks


# --------------------------------------------------------------------------- #
# Master data
# --------------------------------------------------------------------------- #
def clean_master_data(
    frames: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], list[CheckResult]]:
    """Trim master data and verify keys, required fields and domain values."""
    keys = {
        "business_units": "business_unit_code",
        "products": "product_code",
        "cost_centers": "cost_center_code",
        "chart_of_accounts": "account_code",
    }
    cleaned = {name: frames[name].apply(lambda column: column.str.strip()) for name in keys}
    checks: list[CheckResult] = []
    for name, key in keys.items():
        frame = cleaned[name]
        checks.append(
            dq.dataset_check(
                code=f"MASTER_{name.upper()}_KEY_UNIQUE",
                name=f"{name}: natural key {key} is unique and never blank",
                dataset=MASTER,
                quality_dimension="uniqueness",
                stage=dq.SOURCE,
                rows_checked=len(frame),
                rows_failed=int((frame[key].duplicated(keep=False) | (frame[key] == "")).sum()),
            )
        )
        checks.append(
            dq.dataset_check(
                code=f"MASTER_{name.upper()}_REQUIRED",
                name=f"{name}: every attribute is populated",
                dataset=MASTER,
                quality_dimension="completeness",
                stage=dq.SOURCE,
                rows_checked=len(frame),
                rows_failed=int((frame == "").any(axis=1).sum()),
            )
        )

    products = cleaned["products"]
    names_per_category = products.groupby("category_code")["category_name"].transform("nunique")
    checks.append(
        dq.dataset_check(
            code="MASTER_CATEGORY_NAME_DEPENDENCY",
            name="products: each category code maps to exactly one category name",
            dataset=MASTER,
            quality_dimension="consistency",
            stage=dq.SOURCE,
            rows_checked=len(products),
            rows_failed=int((names_per_category > 1).sum()),
        )
    )
    accounts = cleaned["chart_of_accounts"]
    checks.append(
        dq.dataset_check(
            code="MASTER_ACCOUNT_TYPE_DOMAIN",
            name="chart_of_accounts: account_type belongs to the allowed domain",
            dataset=MASTER,
            quality_dimension="validity",
            stage=dq.SOURCE,
            rows_checked=len(accounts),
            rows_failed=int((~accounts["account_type"].isin(ACCOUNT_TYPES)).sum()),
        )
    )

    products = products.astype({"list_price": float, "standard_unit_cost": float})
    accounts = accounts.astype({"statement_order": int})
    return {**cleaned, "products": products, "chart_of_accounts": accounts}, checks


# --------------------------------------------------------------------------- #
# Fact extracts
# --------------------------------------------------------------------------- #
def clean_sales(raw: pd.DataFrame, master: dict[str, pd.DataFrame]) -> CleanExtract:
    unit_codes = set(master["business_units"]["business_unit_code"])
    product_codes = set(master["products"]["product_code"])
    amounts = ["gross_sales_amount", "discount_amount", "net_sales_amount", "cogs_amount"]

    standardised, changed = _standardise(
        raw, ["business_unit_code", "product_code"], "transaction_date"
    )
    rules = [
        RowRule(
            "SALES_REQUIRED_FIELDS",
            "Every field is populated",
            "completeness",
            lambda f: _any_blank(f, list(f.columns)),
        ),
        RowRule(
            "SALES_VALID_DATE",
            "transaction_date is a valid calendar date",
            "validity",
            lambda f: _not_a_date(f["transaction_date"]),
        ),
        RowRule(
            "SALES_VALID_AMOUNTS",
            "units_sold is a positive integer and amounts are non-negative numbers",
            "validity",
            lambda f: (
                _not_a_positive_integer(f["units_sold"]) | _negative_or_not_numeric(f, amounts)
            ),
        ),
        RowRule(
            "SALES_KNOWN_BUSINESS_UNIT",
            "business_unit_code exists in master data",
            "integrity",
            lambda f: ~f["business_unit_code"].isin(unit_codes),
        ),
        RowRule(
            "SALES_KNOWN_PRODUCT",
            "product_code exists in master data",
            "integrity",
            lambda f: ~f["product_code"].isin(product_codes),
        ),
        RowRule(
            "SALES_NET_IDENTITY",
            "net_sales_amount = gross_sales_amount - discount_amount",
            "consistency",
            lambda f: (
                (
                    _number(f["net_sales_amount"])
                    - (_number(f["gross_sales_amount"]) - _number(f["discount_amount"]))
                ).abs()
                > 0.005
            ),
        ),
    ]
    key = ["transaction_date", "business_unit_code", "product_code"]
    valid, rejected, duplicates, checks = _finish(
        SALES,
        "SALES",
        raw,
        standardised,
        changed,
        rules,
        key,
        "Codes are trimmed and upper-cased",
    )
    typed = valid.assign(
        transaction_date=pd.to_datetime(valid["transaction_date"], format=_ISO_DATE),
        units_sold=valid["units_sold"].astype(float).astype("int64"),
        **{column: valid[column].astype(float).round(2) for column in amounts},
    )
    return CleanExtract(SALES, typed, rejected, len(raw), changed, duplicates, checks)


def clean_expenses(raw: pd.DataFrame, master: dict[str, pd.DataFrame]) -> CleanExtract:
    unit_codes = set(master["business_units"]["business_unit_code"])
    center_codes = set(master["cost_centers"]["cost_center_code"])
    accounts = master["chart_of_accounts"]
    operating_accounts = set(
        accounts.loc[accounts["account_type"] == OPERATING_EXPENSE, "account_code"]
    )

    standardised, changed = _standardise(
        raw, ["business_unit_code", "cost_center_code", "entry_id"], "posting_date"
    )
    rules = [
        RowRule(
            "EXPENSES_REQUIRED_FIELDS",
            "Every field is populated",
            "completeness",
            lambda f: _any_blank(f, list(f.columns)),
        ),
        RowRule(
            "EXPENSES_VALID_DATE",
            "posting_date is a valid calendar date",
            "validity",
            lambda f: _not_a_date(f["posting_date"]),
        ),
        RowRule(
            "EXPENSES_POSITIVE_AMOUNT",
            "amount is a number greater than zero",
            "validity",
            lambda f: ~(_number(f["amount"]) > 0),
        ),
        RowRule(
            "EXPENSES_KNOWN_BUSINESS_UNIT",
            "business_unit_code exists in master data",
            "integrity",
            lambda f: ~f["business_unit_code"].isin(unit_codes),
        ),
        RowRule(
            "EXPENSES_KNOWN_COST_CENTER",
            "cost_center_code exists in master data",
            "integrity",
            lambda f: ~f["cost_center_code"].isin(center_codes),
        ),
        RowRule(
            "EXPENSES_OPERATING_ACCOUNT",
            "account_code is an operating-expense account of the chart of accounts",
            "integrity",
            lambda f: ~f["account_code"].isin(operating_accounts),
        ),
    ]
    valid, rejected, duplicates, checks = _finish(
        EXPENSES,
        "EXPENSES",
        raw,
        standardised,
        changed,
        rules,
        ["entry_id"],
        "Codes are trimmed and dates converted to ISO format",
    )
    typed = valid.assign(
        posting_date=pd.to_datetime(valid["posting_date"], format=_ISO_DATE),
        amount=valid["amount"].astype(float).round(2),
    )
    return CleanExtract(EXPENSES, typed, rejected, len(raw), changed, duplicates, checks)


def clean_budget(raw: pd.DataFrame, master: dict[str, pd.DataFrame]) -> CleanExtract:
    unit_codes = set(master["business_units"]["business_unit_code"])
    account_codes = set(master["chart_of_accounts"]["account_code"])

    standardised, changed = _standardise(raw, ["business_unit_code"])
    rules = [
        RowRule(
            "BUDGET_REQUIRED_FIELDS",
            "Every field is populated",
            "completeness",
            lambda f: _any_blank(f, list(f.columns)),
        ),
        RowRule(
            "BUDGET_VALID_PERIOD",
            "fiscal_year is an integer and fiscal_month is between 1 and 12",
            "validity",
            lambda f: (
                _not_a_positive_integer(f["fiscal_year"])
                | _not_a_positive_integer(f["fiscal_month"])
                | (_number(f["fiscal_month"]) > 12)
            ),
        ),
        RowRule(
            "BUDGET_VALID_AMOUNT",
            "budget_amount is a non-negative number",
            "validity",
            lambda f: _negative_or_not_numeric(f, ["budget_amount"]),
        ),
        RowRule(
            "BUDGET_KNOWN_BUSINESS_UNIT",
            "business_unit_code exists in master data",
            "integrity",
            lambda f: ~f["business_unit_code"].isin(unit_codes),
        ),
        RowRule(
            "BUDGET_KNOWN_ACCOUNT",
            "account_code exists in the chart of accounts",
            "integrity",
            lambda f: ~f["account_code"].isin(account_codes),
        ),
    ]
    key = ["fiscal_year", "fiscal_month", "business_unit_code", "account_code"]
    valid, rejected, duplicates, checks = _finish(
        BUDGET,
        "BUDGET",
        raw,
        standardised,
        changed,
        rules,
        key,
        "Codes are trimmed and upper-cased",
    )
    typed = valid.assign(
        fiscal_year=valid["fiscal_year"].astype(int),
        fiscal_month=valid["fiscal_month"].astype(int),
        budget_amount=valid["budget_amount"].astype(float).round(2),
    )
    typed["month_start"] = pd.to_datetime(
        {"year": typed["fiscal_year"], "month": typed["fiscal_month"], "day": 1}
    )

    # A budget is only usable if every month x unit x account cell of its years exists.
    years = typed["fiscal_year"].nunique()
    expected_cells = years * 12 * len(unit_codes) * len(account_codes)
    checks.append(
        dq.dataset_check(
            code="BUDGET_GRID_COMPLETE",
            name="Every month x business unit x account of each budgeted year has a line",
            dataset=BUDGET,
            quality_dimension="completeness",
            stage=dq.SOURCE,
            rows_checked=expected_cells,
            rows_failed=max(expected_cells - len(typed), 0),
        )
    )
    return CleanExtract(BUDGET, typed, rejected, len(raw), changed, duplicates, checks)


# --------------------------------------------------------------------------- #
# Date dimension
# --------------------------------------------------------------------------- #
def build_dim_date(start: date | pd.Timestamp, end: date | pd.Timestamp) -> pd.DataFrame:
    """One row per day covering whole months between start and end (inclusive)."""
    first = pd.Timestamp(start).replace(day=1)
    last = pd.Timestamp(end) + pd.offsets.MonthEnd(0)
    days = pd.date_range(first, last, freq="D")
    month_start = days.to_period("M").to_timestamp()
    return pd.DataFrame(
        {
            "date_key": date_key(days),
            "full_date": days.date,
            "year": days.year,
            "quarter": days.quarter,
            "quarter_label": [f"{d.year}-Q{d.quarter}" for d in days],
            "month": days.month,
            "month_name": days.strftime("%B"),
            "month_short": days.strftime("%b"),
            "year_month": days.strftime("%Y-%m"),
            "month_start_date": month_start.date,
            "month_start_key": date_key(month_start),
            "day_of_month": days.day,
            "day_of_week": days.weekday + 1,
            "day_name": days.strftime("%A"),
            "is_weekend": days.weekday >= 5,
            "is_month_start": days.day == 1,
        }
    )


def date_key(dates: pd.DatetimeIndex | pd.Series) -> pd.Series | pd.Index:
    """Integer YYYYMMDD key for a series of timestamps."""
    accessor = dates.dt if isinstance(dates, pd.Series) else dates
    return accessor.year * 10000 + accessor.month * 100 + accessor.day
