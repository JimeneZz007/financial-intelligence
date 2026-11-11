"""Analysis context: the validated global filters plus lazily loaded data frames.

One context is built per request. Frames are loaded on first use and shared by every
calculation of that request, so a response is always computed from one consistent read.
"""

from __future__ import annotations

from functools import cached_property

import pandas as pd
from sqlalchemy.orm import Session

from backend.app.analytics.periods import ComparisonMode, Period, month_key, parse_month
from backend.app.repositories import warehouse
from backend.app.schemas import AppliedFilters

DEFAULT_PERIOD_MONTHS = 12


class FilterError(ValueError):
    """A filter value is syntactically valid but not applicable to the available data."""


class DataNotLoadedError(RuntimeError):
    """The warehouse is empty: the ETL pipeline has not been run."""


class AnalysisContext:
    def __init__(
        self,
        session: Session,
        period: Period,
        business_units: list[str],
        compare: ComparisonMode,
        available: Period,
    ) -> None:
        self.session = session
        self.period = period
        self.business_units = business_units  # empty list = every business unit
        self.compare: ComparisonMode = compare
        self.available = available

    # --- periods -------------------------------------------------------------------
    @cached_property
    def comparison_period(self) -> Period | None:
        """The comparison period, or None when it is not fully inside the available data."""
        candidate = self.period.comparison(self.compare)
        return candidate if candidate.is_within(self.available) else None

    @property
    def comparison_name(self) -> str:
        return "prior year" if self.compare == "previous_year" else "prior period"

    # --- account-level frames (actual and budget) -----------------------------------
    @cached_property
    def history(self) -> pd.DataFrame:
        return warehouse.account_month_frame(self.session, self.business_units)

    @cached_property
    def current(self) -> pd.DataFrame:
        return self.period.select(self.history)

    @cached_property
    def comparison(self) -> pd.DataFrame | None:
        period = self.comparison_period
        return None if period is None else period.select(self.history)

    # --- sales frames (product level) -------------------------------------------------
    @cached_property
    def sales_history(self) -> pd.DataFrame:
        return warehouse.sales_month_product_frame(self.session, self.business_units)

    @cached_property
    def sales_current(self) -> pd.DataFrame:
        return self.period.select(self.sales_history)

    @cached_property
    def sales_comparison(self) -> pd.DataFrame | None:
        period = self.comparison_period
        return None if period is None else period.select(self.sales_history)

    # --- expense frames (cost-centre level) -------------------------------------------
    @cached_property
    def expenses_history(self) -> pd.DataFrame:
        return warehouse.expense_month_center_frame(self.session, self.business_units)

    @cached_property
    def expenses_current(self) -> pd.DataFrame:
        return self.period.select(self.expenses_history)

    @cached_property
    def expenses_comparison(self) -> pd.DataFrame | None:
        period = self.comparison_period
        return None if period is None else period.select(self.expenses_history)

    # --- echo ---------------------------------------------------------------------------
    def applied_filters(self) -> AppliedFilters:
        comparison = self.comparison_period
        return AppliedFilters(
            start=month_key(self.period.start),
            end=month_key(self.period.end),
            months=self.period.n_months,
            period_label=self.period.label,
            business_units=self.business_units,
            compare=self.compare,
            comparison_available=comparison is not None,
            comparison_start=month_key(comparison.start) if comparison else None,
            comparison_end=month_key(comparison.end) if comparison else None,
            comparison_label=comparison.label if comparison else None,
        )


def build_context(
    session: Session,
    start: str | None,
    end: str | None,
    business_units: list[str] | None,
    compare: ComparisonMode,
) -> AnalysisContext:
    """Validate the global filters against the data and build the context."""
    available = warehouse.available_period(session)
    if available is None:
        raise DataNotLoadedError("The warehouse is empty. Run the ETL pipeline first.")

    try:
        end_month = parse_month(end) if end else available.end
        if start:
            start_month = parse_month(start)
        else:
            start_month = max(
                available.start, end_month - pd.DateOffset(months=DEFAULT_PERIOD_MONTHS - 1)
            )
        period = Period(start_month, end_month)
    except ValueError as error:
        raise FilterError(str(error)) from error
    if not period.is_within(available):
        raise FilterError(
            f"Period {month_key(period.start)}..{month_key(period.end)} is outside the "
            f"available data ({month_key(available.start)}..{month_key(available.end)})"
        )

    known = [unit["code"] for unit in warehouse.business_units(session)]
    requested = list(dict.fromkeys(code.strip().upper() for code in business_units or []))
    unknown = [code for code in requested if code not in known]
    if unknown:
        raise FilterError(
            f"Unknown business unit(s): {', '.join(unknown)}. Valid codes: {', '.join(known)}"
        )
    # Selecting every unit is the same as not filtering.
    selected = [] if set(requested) == set(known) else [c for c in known if c in requested]
    return AnalysisContext(session, period, selected, compare, available)
