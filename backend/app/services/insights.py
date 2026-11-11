"""Findings computed from the filtered data.

Every sentence is assembled from numbers calculated for the current filters; nothing is
written by hand per scenario and nothing reads the generator's scenario definitions.
The wording describes arithmetic facts ("largest contribution", "exceeded budget") and
deliberately avoids causal claims.
"""

from __future__ import annotations

from backend.app.analytics.metrics import (
    OPERATING_EXPENSE,
    pct_change,
    profit_and_loss,
    safe_ratio,
    statement_by,
)
from backend.app.schemas import Evidence, Insight, InsightsResponse
from backend.app.services import analysis
from backend.app.services.budget import account_variances
from backend.app.services.context import AnalysisContext
from backend.app.services.formatting import money, ratio

MIN_MONTHS_FOR_TREND = 3


# --------------------------------------------------------------------------- #
# Text formatting
# --------------------------------------------------------------------------- #
def usd(value: float, *, signed: bool = False) -> str:
    """Compact currency: $1.2M, $345K, $980."""
    magnitude = abs(value)
    if magnitude >= 1_000_000:
        text = f"${magnitude / 1_000_000:.1f}M"
    elif magnitude >= 1_000:
        text = f"${magnitude / 1_000:.0f}K"
    else:
        text = f"${magnitude:.0f}"
    if value < 0:
        return f"-{text}"
    return f"+{text}" if signed else text


def pct(value: float, *, signed: bool = False) -> str:
    return f"{value * 100:+.1f}%" if signed else f"{value * 100:.1f}%"


def points(value: float) -> str:
    return f"{value * 100:+.1f} pp"


def _tone(is_good: bool | None) -> str:
    if is_good is None:
        return "neutral"
    return "positive" if is_good else "negative"


def _evidence(label: str, value: float | None, unit: str) -> Evidence:
    rounded = None if value is None else (ratio(value) if unit == "percent" else money(value))
    return Evidence(label=label, value=rounded, unit=unit)


# --------------------------------------------------------------------------- #
# Individual findings
# --------------------------------------------------------------------------- #
def _operating_income(ctx: AnalysisContext) -> Insight:
    current = profit_and_loss(ctx.current)
    margin = current.operating_margin
    if ctx.comparison is None or ctx.comparison_period is None:
        return Insight(
            id="operating_income",
            category="performance",
            tone="neutral",
            title=f"Operating income of {usd(current.operating_income)} in the period",
            detail=(
                f"Operating margin was {pct(margin or 0.0)} on net revenue of "
                f"{usd(current.net_revenue)}. No {ctx.comparison_name} data is available "
                "for a comparison."
            ),
            evidence=[
                _evidence("Operating income", current.operating_income, "currency"),
                _evidence("Operating margin", margin, "percent"),
            ],
        )

    previous = profit_and_loss(ctx.comparison)
    change = current.operating_income - previous.operating_income
    relative = pct_change(current.operating_income, previous.operating_income)
    bridge = [s for s in analysis.income_bridge(ctx, "comparison").steps if s.kind == "effect"]
    best = max(bridge, key=lambda s: s.amount)
    worst = min(bridge, key=lambda s: s.amount)
    direction = "rose" if change > 0 else "fell"
    relative_text = f" ({pct(relative, signed=True)})" if relative is not None else ""
    return Insight(
        id="operating_income",
        category="performance",
        tone=_tone(change > 0) if change else "neutral",
        title=(
            f"Operating income {direction} {usd(abs(change))}{relative_text} "
            f"versus {ctx.comparison_name}"
        ),
        detail=(
            f"It reached {usd(current.operating_income)} against "
            f"{usd(previous.operating_income)} in {ctx.comparison_period.label}. "
            f"Largest positive contribution: {best.label} ({usd(best.amount, signed=True)}); "
            f"largest negative: {worst.label} ({usd(worst.amount, signed=True)})."
        ),
        evidence=[
            _evidence("Operating income", current.operating_income, "currency"),
            _evidence(
                f"Operating income, {ctx.comparison_name}", previous.operating_income, "currency"
            ),
            _evidence("Change", change, "currency"),
            _evidence("Change %", relative, "percent"),
        ],
    )


def _budget_headlines(ctx: AnalysisContext) -> list[Insight]:
    actual = profit_and_loss(ctx.current, "actual")
    budget = profit_and_loss(ctx.current, "budget")
    insights: list[Insight] = []

    revenue_gap = actual.net_revenue - budget.net_revenue
    revenue_gap_pct = pct_change(actual.net_revenue, budget.net_revenue) or 0.0
    side = "above" if revenue_gap > 0 else "below"
    insights.append(
        Insight(
            id="revenue_vs_budget",
            category="budget",
            tone=_tone(revenue_gap > 0),
            title=f"Net revenue finished {pct(abs(revenue_gap_pct))} {side} budget",
            detail=(
                f"{usd(actual.net_revenue)} actual against {usd(budget.net_revenue)} budgeted, "
                f"a difference of {usd(revenue_gap, signed=True)}."
            ),
            evidence=[
                _evidence("Actual", actual.net_revenue, "currency"),
                _evidence("Budget", budget.net_revenue, "currency"),
                _evidence("Variance", revenue_gap, "currency"),
                _evidence("Variance %", revenue_gap_pct, "percent"),
            ],
        )
    )

    income_gap = actual.operating_income - budget.operating_income
    income_gap_pct = pct_change(actual.operating_income, budget.operating_income)
    bridge = [s for s in analysis.income_bridge(ctx, "budget").steps if s.kind == "effect"]
    best = max(bridge, key=lambda s: s.amount)
    worst = min(bridge, key=lambda s: s.amount)
    side = "above" if income_gap > 0 else "below"
    insights.append(
        Insight(
            id="operating_income_vs_budget",
            category="budget",
            tone=_tone(income_gap > 0),
            title=f"Operating income was {usd(abs(income_gap))} {side} budget",
            detail=(
                f"{usd(actual.operating_income)} actual against {usd(budget.operating_income)} "
                f"budgeted. Largest favorable line: {best.label} "
                f"({usd(best.amount, signed=True)}); largest unfavorable: {worst.label} "
                f"({usd(worst.amount, signed=True)})."
            ),
            evidence=[
                _evidence("Actual", actual.operating_income, "currency"),
                _evidence("Budget", budget.operating_income, "currency"),
                _evidence("Variance", income_gap, "currency"),
                _evidence("Variance %", income_gap_pct, "percent"),
            ],
        )
    )
    return insights


def _expense_variances(ctx: AnalysisContext) -> list[Insight]:
    accounts = account_variances(ctx.current)
    opex = accounts[accounts["account_type"] == OPERATING_EXPENSE].assign(
        variance=lambda f: f["actual"] - f["budget"]
    )
    insights: list[Insight] = []

    overruns = opex[opex["variance"] > 0]
    if not overruns.empty:
        top = overruns.loc[overruns["variance"].idxmax()]
        share = safe_ratio(top["variance"], overruns["variance"].sum()) or 0.0
        insights.append(
            Insight(
                id="largest_expense_overrun",
                category="expenses",
                tone="negative",
                title=(
                    f"{top['account_name']} exceeded budget by {usd(top['variance'])} "
                    f"({pct(top['variance'] / top['budget'], signed=True)})"
                ),
                detail=(
                    f"It is the largest unfavorable operating-expense variance and represents "
                    f"{pct(share)} of all expense overruns in the period "
                    f"({usd(overruns['variance'].sum())} across {len(overruns)} accounts)."
                ),
                evidence=[
                    _evidence("Actual", top["actual"], "currency"),
                    _evidence("Budget", top["budget"], "currency"),
                    _evidence("Variance", top["variance"], "currency"),
                    _evidence("Share of overruns", share, "percent"),
                ],
            )
        )

    savings = opex[opex["variance"] < 0]
    if not savings.empty:
        top = savings.loc[savings["variance"].idxmin()]
        insights.append(
            Insight(
                id="largest_expense_saving",
                category="expenses",
                tone="positive",
                title=(
                    f"{top['account_name']} came in {usd(abs(top['variance']))} under budget "
                    f"({pct(top['variance'] / top['budget'], signed=True)})"
                ),
                detail=(
                    f"It is the largest favorable operating-expense variance. Accounts under "
                    f"budget total {usd(abs(savings['variance'].sum()))} in the period."
                ),
                evidence=[
                    _evidence("Actual", top["actual"], "currency"),
                    _evidence("Budget", top["budget"], "currency"),
                    _evidence("Variance", top["variance"], "currency"),
                ],
            )
        )
    return insights


def _business_units(ctx: AnalysisContext) -> list[Insight]:
    by_unit = statement_by(ctx.current, ["business_unit_name"])
    if len(by_unit) < 2:
        return []
    total_revenue = by_unit["net_revenue"].sum()
    leader = by_unit["net_revenue"].idxmax()
    best_margin = by_unit["operating_margin"].idxmax()
    worst_margin = by_unit["operating_margin"].idxmin()
    share = safe_ratio(by_unit.at[leader, "net_revenue"], total_revenue) or 0.0
    insights = [
        Insight(
            id="top_business_unit",
            category="performance",
            tone="neutral",
            title=f"{leader} generated {pct(share)} of net revenue",
            detail=(
                f"Highest operating margin: {best_margin} "
                f"({pct(by_unit.at[best_margin, 'operating_margin'])}); lowest: {worst_margin} "
                f"({pct(by_unit.at[worst_margin, 'operating_margin'])})."
            ),
            evidence=[
                _evidence(f"{leader} net revenue", by_unit.at[leader, "net_revenue"], "currency"),
                _evidence("Share of revenue", share, "percent"),
                _evidence(
                    f"{best_margin} operating margin",
                    by_unit.at[best_margin, "operating_margin"],
                    "percent",
                ),
                _evidence(
                    f"{worst_margin} operating margin",
                    by_unit.at[worst_margin, "operating_margin"],
                    "percent",
                ),
            ],
        )
    ]
    if ctx.comparison is not None:
        previous = statement_by(ctx.comparison, ["business_unit_name"])["net_revenue"]
        growth = ((by_unit["net_revenue"] - previous) / previous.abs()).dropna()
        if not growth.empty:
            fastest, slowest = growth.idxmax(), growth.idxmin()
            insights.append(
                Insight(
                    id="revenue_growth_by_unit",
                    category="trend",
                    tone=_tone(growth[fastest] > 0),
                    title=(
                        f"{fastest} had the strongest revenue growth: "
                        f"{pct(growth[fastest], signed=True)} versus {ctx.comparison_name}"
                    ),
                    detail=(
                        f"The weakest was {slowest} ({pct(growth[slowest], signed=True)}). "
                        f"Total net revenue changed "
                        f"{pct(pct_change(total_revenue, previous.sum()) or 0.0, signed=True)}."
                    ),
                    evidence=[
                        _evidence(f"{fastest} growth", growth[fastest], "percent"),
                        _evidence(f"{slowest} growth", growth[slowest], "percent"),
                    ],
                )
            )
    return insights


def _profitability(ctx: AnalysisContext) -> list[Insight]:
    insights: list[Insight] = []
    by_category = ctx.sales_current.groupby("category_name", observed=True)[
        ["net_revenue", "direct_costs"]
    ].sum()
    if len(by_category) >= 2:
        margins = 1 - by_category["direct_costs"] / by_category["net_revenue"]
        best, worst = margins.idxmax(), margins.idxmin()
        worst_share = by_category.at[worst, "net_revenue"] / by_category["net_revenue"].sum()
        insights.append(
            Insight(
                id="category_margins",
                category="profitability",
                tone="neutral",
                title=f"{best} has the highest gross margin ({pct(margins[best])})",
                detail=(
                    f"{worst} has the lowest ({pct(margins[worst])}) while contributing "
                    f"{pct(worst_share)} of net revenue."
                ),
                evidence=[
                    _evidence(f"{best} gross margin", margins[best], "percent"),
                    _evidence(f"{worst} gross margin", margins[worst], "percent"),
                ],
            )
        )

    drivers = analysis.margin_drivers(ctx, "category")
    if drivers.available and drivers.margin_change is not None and drivers.rows:
        main = max(drivers.rows, key=lambda r: abs(r.total_effect))
        direction = "rose" if drivers.margin_change > 0 else "fell"
        base_margin, current_margin = drivers.base_margin or 0.0, drivers.current_margin or 0.0
        rate_effect, mix_effect = drivers.rate_effect or 0.0, drivers.mix_effect or 0.0
        insights.append(
            Insight(
                id="gross_margin_drivers",
                category="profitability",
                tone=_tone(drivers.margin_change > 0) if drivers.margin_change else "neutral",
                title=(
                    f"Gross margin {direction} {abs(drivers.margin_change) * 100:.1f} pp "
                    f"versus {ctx.comparison_name}"
                ),
                detail=(
                    f"From {pct(base_margin)} to {pct(current_margin)}. "
                    f"Rate effect (margins within categories): {points(rate_effect)}; "
                    f"mix effect (shift between categories): {points(mix_effect)}. "
                    f"Largest single contribution: {main.label} ({points(main.total_effect)})."
                ),
                evidence=[
                    _evidence("Gross margin", drivers.current_margin, "percent"),
                    _evidence(
                        f"Gross margin, {ctx.comparison_name}", drivers.base_margin, "percent"
                    ),
                    _evidence("Rate effect", drivers.rate_effect, "percent"),
                    _evidence("Mix effect", drivers.mix_effect, "percent"),
                ],
            )
        )

    pvm = analysis.price_volume_mix_analysis(ctx, "category").total
    if pvm is not None:
        insights.append(
            Insight(
                id="revenue_price_volume_mix",
                category="performance",
                tone=_tone(pvm.total_change > 0) if pvm.total_change else "neutral",
                title=(
                    f"Net revenue changed {usd(pvm.total_change, signed=True)} "
                    f"versus {ctx.comparison_name}"
                ),
                detail=(
                    f"Decomposition: volume {usd(pvm.volume_effect, signed=True)}, "
                    f"price {usd(pvm.price_effect, signed=True)} and "
                    f"mix {usd(pvm.mix_effect, signed=True)}."
                ),
                evidence=[
                    _evidence("Volume effect", pvm.volume_effect, "currency"),
                    _evidence("Price effect", pvm.price_effect, "currency"),
                    _evidence("Mix effect", pvm.mix_effect, "currency"),
                    _evidence("Total change", pvm.total_change, "currency"),
                ],
            )
        )
    return insights


def _anomalies(ctx: AnalysisContext) -> Insight:
    found = analysis.anomalies_in_period(ctx)
    material = found[found["is_material"]]
    if material.empty:
        return Insight(
            id="anomalies",
            category="anomaly",
            tone="neutral",
            title="No material anomalies in the period",
            detail=(
                "No business unit and account shows a budget variance that is both "
                "statistically unusual for its own history and financially material."
            ),
            evidence=[_evidence("Material anomalies", 0, "number")],
        )
    top = material.iloc[material["robust_z"].abs().to_numpy().argmax()]
    side = "above" if top["variance"] > 0 else "below"
    unfavorable = sum(
        analysis.anomaly_item(row).status == "unfavorable" for _, row in material.iterrows()
    )
    count = len(material)
    return Insight(
        id="anomalies",
        category="anomaly",
        tone="negative" if unfavorable > count / 2 else "neutral",
        title=f"{count} material {'anomaly' if count == 1 else 'anomalies'} in the period",
        detail=(
            f"{unfavorable} unfavorable and {count - unfavorable} favorable. Most extreme: "
            f"{top['business_unit_name']} - {top['account_name']} in "
            f"{top['month'].strftime('%b %Y')}, {pct(abs(top['variance_pct']))} {side} budget "
            f"(robust z = {top['robust_z']:+.1f})."
        ),
        evidence=[
            _evidence("Material anomalies", count, "number"),
            _evidence("Unfavorable", unfavorable, "number"),
            _evidence("Most extreme variance", top["variance"], "currency"),
            _evidence("Most extreme variance %", top["variance_pct"], "percent"),
        ],
    )


def _trend(ctx: AnalysisContext) -> list[Insight]:
    if ctx.period.n_months < MIN_MONTHS_FOR_TREND:
        return []
    actual = statement_by(ctx.current, ["month"], "actual")
    budget = statement_by(ctx.current, ["month"], "budget")
    below = actual["net_revenue"] < budget["net_revenue"]
    best, worst = actual["operating_margin"].idxmax(), actual["operating_margin"].idxmin()

    # Longest run of consecutive months with revenue below budget.
    runs = (below != below.shift()).cumsum()
    longest = int(below.groupby(runs).sum().max())
    months_below = int(below.sum())
    return [
        Insight(
            id="monthly_pattern",
            category="trend",
            tone="neutral",
            title=(
                f"Operating margin peaked in {best.strftime('%b %Y')} "
                f"({pct(actual.at[best, 'operating_margin'])})"
            ),
            detail=(
                f"The lowest month was {worst.strftime('%b %Y')} "
                f"({pct(actual.at[worst, 'operating_margin'])}). Net revenue was below budget in "
                f"{months_below} of {len(actual)} months; the longest consecutive run was "
                f"{longest} {'month' if longest == 1 else 'months'}."
            ),
            evidence=[
                _evidence(
                    "Highest monthly operating margin",
                    actual.at[best, "operating_margin"],
                    "percent",
                ),
                _evidence(
                    "Lowest monthly operating margin",
                    actual.at[worst, "operating_margin"],
                    "percent",
                ),
                _evidence("Months below revenue budget", months_below, "number"),
                _evidence("Longest run below budget", longest, "number"),
            ],
        )
    ]


def build_insights(ctx: AnalysisContext) -> InsightsResponse:
    if ctx.current.empty:
        return InsightsResponse(filters=ctx.applied_filters(), insights=[])
    insights: list[Insight] = [
        _operating_income(ctx),
        *_budget_headlines(ctx),
        *_expense_variances(ctx),
        *_business_units(ctx),
        *_profitability(ctx),
        _anomalies(ctx),
        *_trend(ctx),
    ]
    return InsightsResponse(filters=ctx.applied_filters(), insights=insights)
