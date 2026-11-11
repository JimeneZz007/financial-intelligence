"""Controlled data-quality defects injected into the raw extracts.

Real extracts are never clean, so the ETL must prove it can standardise, deduplicate and
quarantine bad rows. Defects are *additive or recoverable*: junk rows are extra rows and
format defects can be undone, so the clean dataset (and its control totals) is always
fully recoverable. Frames handled here contain strings only, exactly as written to CSV.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Number of rows affected by each defect type.
SALES_DEFECTS = {
    "DUPLICATE_ROW": 40,
    "CODE_FORMAT": 25,
    "UNKNOWN_PRODUCT": 12,
    "MISSING_UNITS": 8,
    "AMOUNT_MISMATCH": 6,
}
EXPENSE_DEFECTS = {
    "DUPLICATE_ROW": 15,
    "DATE_FORMAT": 9,
    "NON_POSITIVE_AMOUNT": 10,
    "UNKNOWN_COST_CENTER": 5,
}
BUDGET_DEFECTS = {"DUPLICATE_ROW": 3}


def _sample(frame: pd.DataFrame, count: int, rng: np.random.Generator) -> pd.DataFrame:
    return frame.iloc[rng.choice(len(frame), count, replace=False)].copy()


def _interleave(
    clean: pd.DataFrame, extra: list[pd.DataFrame], rng: np.random.Generator
) -> pd.DataFrame:
    """Insert extra rows at random positions, keeping the order of the clean rows."""
    extras = pd.concat(extra, ignore_index=True)
    position = np.concatenate(
        [np.arange(len(clean), dtype=float), rng.uniform(0, len(clean), len(extras))]
    )
    combined = pd.concat([clean, extras], ignore_index=True)
    return combined.iloc[np.argsort(position, kind="stable")].reset_index(drop=True)


def _messy_code(code: str, variant: int) -> str:
    return (code.lower(), f" {code}", f"{code} ", f" {code.lower()} ")[variant % 4]


def inject_sales_defects(clean: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    frame = clean.copy()

    # Recoverable: inconsistent casing / whitespace in the business unit code.
    idx = rng.choice(len(frame), SALES_DEFECTS["CODE_FORMAT"], replace=False)
    column = frame.columns.get_loc("business_unit_code")
    for variant, row in enumerate(idx):
        frame.iat[row, column] = _messy_code(frame.iat[row, column], variant)

    duplicates = _sample(clean, SALES_DEFECTS["DUPLICATE_ROW"], rng)

    unknown_product = _sample(clean, SALES_DEFECTS["UNKNOWN_PRODUCT"], rng)
    unknown_product["product_code"] = unknown_product["product_code"].str.slice(0, 4) + "999"

    missing_units = _sample(clean, SALES_DEFECTS["MISSING_UNITS"], rng)
    missing_units["units_sold"] = ""

    mismatch = _sample(clean, SALES_DEFECTS["AMOUNT_MISMATCH"], rng)
    mismatch["net_sales_amount"] = (mismatch["gross_sales_amount"].astype(float) + 10.0).map(
        "{:.2f}".format
    )

    return _interleave(frame, [duplicates, unknown_product, missing_units, mismatch], rng)


def inject_expense_defects(clean: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    frame = clean.copy()

    # Recoverable: a second date format (DD/MM/YYYY) from a different source system.
    idx = rng.choice(len(frame), EXPENSE_DEFECTS["DATE_FORMAT"], replace=False)
    column = frame.columns.get_loc("posting_date")
    for row in idx:
        year, month, day = frame.iat[row, column].split("-")
        frame.iat[row, column] = f"{day}/{month}/{year}"

    duplicates = _sample(clean, EXPENSE_DEFECTS["DUPLICATE_ROW"], rng)

    non_positive = _sample(clean, EXPENSE_DEFECTS["NON_POSITIVE_AMOUNT"], rng)
    non_positive["amount"] = [
        "0.00" if i % 2 == 0 else f"-{amount}" for i, amount in enumerate(non_positive["amount"])
    ]
    unknown_center = _sample(clean, EXPENSE_DEFECTS["UNKNOWN_COST_CENTER"], rng)
    unknown_center["cost_center_code"] = "ZZZ"

    # Junk rows get their own entry ids so they never collide with valid entries.
    junk = pd.concat([non_positive, unknown_center], ignore_index=True)
    junk["entry_id"] = [f"EXP-9{i:06d}" for i in range(1, len(junk) + 1)]

    return _interleave(frame, [duplicates, junk], rng)


def inject_budget_defects(clean: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    duplicates = _sample(clean, BUDGET_DEFECTS["DUPLICATE_ROW"], rng)
    return _interleave(clean.copy(), [duplicates], rng)
