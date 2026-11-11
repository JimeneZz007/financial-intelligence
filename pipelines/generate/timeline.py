"""Calendar arrays shared by the generators."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Timeline:
    dates: pd.DatetimeIndex  # one entry per day (D)
    year: np.ndarray  # (D,)
    month: np.ndarray  # (D,) 1..12
    weekday: np.ndarray  # (D,) 0 = Monday
    month_index: np.ndarray  # (D,) position of the day's month in `month_keys`
    month_keys: tuple[str, ...]  # (M,) 'YYYY-MM'
    month_year: np.ndarray  # (M,)
    month_number: np.ndarray  # (M,) 1..12

    @property
    def n_days(self) -> int:
        return len(self.dates)

    @property
    def n_months(self) -> int:
        return len(self.month_keys)

    @property
    def first_year(self) -> int:
        return int(self.month_year[0])


def build_timeline(start: date, end: date) -> Timeline:
    dates = pd.date_range(start, end, freq="D")
    periods = dates.to_period("M")
    unique_periods = periods.unique()
    month_keys = tuple(str(p) for p in unique_periods)
    key_position = {key: i for i, key in enumerate(month_keys)}
    return Timeline(
        dates=dates,
        year=dates.year.to_numpy(),
        month=dates.month.to_numpy(),
        weekday=dates.weekday.to_numpy(),
        month_index=np.array([key_position[str(p)] for p in periods]),
        month_keys=month_keys,
        month_year=np.array([p.year for p in unique_periods]),
        month_number=np.array([p.month for p in unique_periods]),
    )
