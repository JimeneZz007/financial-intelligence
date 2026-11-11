"""Core formulas and period arithmetic (pure functions, no database)."""

from __future__ import annotations

import pandas as pd
import pytest

from backend.app.analytics.metrics import (
    ProfitAndLoss,
    favorability,
    pct_change,
    profit_and_loss,
    profit_impact,
    safe_ratio,
    statement_by,
)
from backend.app.analytics.periods import Period, month_key, parse_month


def _accounts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("2024-01-01", "A", "REVENUE", 1000.0, 900.0),
            ("2024-01-01", "A", "DIRECT_COST", 600.0, 540.0),
            ("2024-01-01", "A", "OPERATING_EXPENSE", 250.0, 240.0),
            ("2024-01-01", "A", "OPERATING_EXPENSE", 50.0, 60.0),
            ("2024-02-01", "A", "REVENUE", 500.0, 600.0),
            ("2024-02-01", "A", "DIRECT_COST", 350.0, 360.0),
            ("2024-02-01", "B", "REVENUE", 200.0, 200.0),
        ],
        columns=["month", "unit", "account_type", "actual", "budget"],
    ).assign(month=lambda f: pd.to_datetime(f["month"]))


# --------------------------------------------------------------------------- #
# Ratios and variances
# --------------------------------------------------------------------------- #
def test_safe_ratio_returns_none_instead_of_dividing_by_zero() -> None:
    assert safe_ratio(10, 4) == 2.5
    assert safe_ratio(10, 0) is None
    assert safe_ratio(float("nan"), 2) is None


def test_pct_change_uses_the_absolute_reference() -> None:
    assert pct_change(120, 100) == pytest.approx(0.20)
    assert pct_change(80, 100) == pytest.approx(-0.20)
    # Improving from a loss of 100 to a loss of 50 is a positive change.
    assert pct_change(-50, -100) == pytest.approx(0.50)
    assert pct_change(10, 0) is None


@pytest.mark.parametrize(
    ("variance", "reference", "higher_is_better", "expected"),
    [
        (50, 1000, True, "favorable"),  # revenue above budget
        (-50, 1000, True, "unfavorable"),  # revenue below budget
        (50, 1000, False, "unfavorable"),  # cost above budget
        (-50, 1000, False, "favorable"),  # cost below budget
        (4, 1000, True, "on_target"),  # within the 0.5% tolerance
        (-4, 1000, False, "on_target"),
        (0, 0, True, "on_target"),
        (5, 0, False, "unfavorable"),  # spending with no budget at all
    ],
)
def test_favorability_follows_the_effect_on_profit(
    variance: float, reference: float, higher_is_better: bool, expected: str
) -> None:
    assert favorability(variance, reference, higher_is_better=higher_is_better) == expected


def test_profit_impact_flips_the_sign_of_cost_variances() -> None:
    assert profit_impact(100, higher_is_better=True) == 100
    assert profit_impact(100, higher_is_better=False) == -100


# --------------------------------------------------------------------------- #
# Profit and loss
# --------------------------------------------------------------------------- #
def test_profit_and_loss_identities() -> None:
    pnl = ProfitAndLoss(net_revenue=1000, direct_costs=600, operating_expenses=300)
    assert pnl.gross_profit == 400
    assert pnl.operating_income == 100
    assert pnl.gross_margin == pytest.approx(0.40)
    assert pnl.operating_margin == pytest.approx(0.10)
    assert pnl.opex_ratio == pytest.approx(0.30)


def test_margins_are_undefined_without_revenue() -> None:
    pnl = ProfitAndLoss(net_revenue=0, direct_costs=0, operating_expenses=50)
    assert pnl.gross_margin is None
    assert pnl.operating_margin is None
    assert pnl.operating_income == -50


def test_profit_and_loss_aggregates_by_account_type() -> None:
    january = _accounts()[lambda f: f["month"] == "2024-01-01"]
    actual = profit_and_loss(january, "actual")
    budget = profit_and_loss(january, "budget")
    assert (actual.net_revenue, actual.direct_costs, actual.operating_expenses) == (1000, 600, 300)
    assert actual.operating_income == 100
    assert budget.operating_income == 900 - 540 - 300


def test_statement_by_margin_is_a_ratio_of_sums_not_a_mean_of_ratios() -> None:
    frame = _accounts()
    total = statement_by(frame.assign(all="all"), ["all"]).iloc[0]
    by_month = statement_by(frame, ["month"])
    # 1,700 revenue and 950 direct costs overall.
    assert total["gross_margin"] == pytest.approx((1700 - 950) / 1700)
    assert total["gross_margin"] != pytest.approx(by_month["gross_margin"].mean())


def test_statement_by_handles_groups_without_some_account_types() -> None:
    by_unit = statement_by(_accounts(), ["unit"])
    assert by_unit.at["B", "direct_costs"] == 0
    assert by_unit.at["B", "operating_income"] == 200
    assert by_unit.at["B", "gross_margin"] == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# Periods
# --------------------------------------------------------------------------- #
def test_parse_month_validates_the_format() -> None:
    assert parse_month("2024-03") == pd.Timestamp("2024-03-01")
    for invalid in ("2024-13", "2024-3", "24-03", "2024/03", ""):
        with pytest.raises(ValueError, match="Invalid month"):
            parse_month(invalid)


def test_period_length_and_labels() -> None:
    period = Period(parse_month("2024-11"), parse_month("2025-02"))
    assert period.n_months == 4
    assert [month_key(m) for m in period.months] == ["2024-11", "2024-12", "2025-01", "2025-02"]
    assert period.label == "Nov 2024 - Feb 2025"
    assert Period(parse_month("2024-05"), parse_month("2024-05")).label == "May 2024"


def test_period_rejects_inverted_ranges() -> None:
    with pytest.raises(ValueError, match="start must not be after"):
        Period(parse_month("2024-05"), parse_month("2024-04"))


def test_comparison_periods() -> None:
    quarter = Period(parse_month("2025-04"), parse_month("2025-06"))
    previous_year = quarter.comparison("previous_year")
    previous_period = quarter.comparison("previous_period")
    assert (month_key(previous_year.start), month_key(previous_year.end)) == ("2024-04", "2024-06")
    assert (month_key(previous_period.start), month_key(previous_period.end)) == (
        "2025-01",
        "2025-03",
    )


def test_period_availability_and_selection() -> None:
    available = Period(parse_month("2023-01"), parse_month("2025-12"))
    first_year = Period(parse_month("2023-01"), parse_month("2023-12"))
    assert first_year.is_within(available)
    assert not first_year.comparison("previous_year").is_within(available)

    frame = _accounts()
    selected = Period(parse_month("2024-02"), parse_month("2024-02")).select(frame)
    assert set(selected["month"]) == {pd.Timestamp("2024-02-01")}
