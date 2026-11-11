"""Month-based analysis periods and their comparison periods."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import pandas as pd

ComparisonMode = Literal["previous_year", "previous_period"]

_MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def parse_month(value: str) -> pd.Timestamp:
    """Parse 'YYYY-MM' into the timestamp of the first day of that month."""
    if not _MONTH_PATTERN.match(value):
        raise ValueError(f"Invalid month '{value}': expected YYYY-MM")
    return pd.Timestamp(f"{value}-01")


def month_key(month: pd.Timestamp) -> str:
    return month.strftime("%Y-%m")


@dataclass(frozen=True)
class Period:
    """An inclusive range of whole months."""

    start: pd.Timestamp
    end: pd.Timestamp

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError("Period start must not be after its end")

    @property
    def months(self) -> pd.DatetimeIndex:
        return pd.date_range(self.start, self.end, freq="MS")

    @property
    def n_months(self) -> int:
        return len(self.months)

    @property
    def label(self) -> str:
        if self.start == self.end:
            return self.start.strftime("%b %Y")
        return f"{self.start.strftime('%b %Y')} - {self.end.strftime('%b %Y')}"

    def shift(self, months: int) -> Period:
        offset = pd.DateOffset(months=months)
        return Period(self.start + offset, self.end + offset)

    def comparison(self, mode: ComparisonMode) -> Period:
        """Same months one year earlier, or the equally long period just before."""
        return self.shift(-12 if mode == "previous_year" else -self.n_months)

    def is_within(self, available: Period) -> bool:
        return self.start >= available.start and self.end <= available.end

    def select(self, frame: pd.DataFrame, column: str = "month") -> pd.DataFrame:
        return frame[(frame[column] >= self.start) & (frame[column] <= self.end)]
