"""Contribution analysis (bridge, price-volume-mix, margin drivers) and anomalies."""

from __future__ import annotations

import pandas as pd

from backend.app.analytics import anomalies as anomaly_model
from backend.app.analytics.contribution import (
    PVM_COLUMNS,
    margin_mix_rate,
    operating_income_bridge,
    price_volume_mix,
)
from backend.app.analytics.metrics import REVENUE, favorability, safe_ratio
from backend.app.analytics.periods import month_key
from backend.app.schemas import (
    AnomaliesResponse,
    Anomaly,
    AnomalyMethod,
    BridgeResponse,
    BridgeStepItem,
    MarginDriverRow,
    MarginDriversResponse,
    PvmResponse,
    PvmRow,
)
from backend.app.services.context import AnalysisContext
from backend.app.services.formatting import money, ratio

SEGMENTS: dict[str, tuple[str, str]] = {
    "category": ("category_code", "category_name"),
    "business_unit": ("business_unit_code", "business_unit_name"),
}


# --------------------------------------------------------------------------- #
# Operating income bridge
# --------------------------------------------------------------------------- #
def income_bridge(ctx: AnalysisContext, basis: str) -> BridgeResponse:
    if basis == "budget":
        steps = operating_income_bridge(
            ctx.current,
            ctx.current,
            base_column="budget",
            base_label="Budget",
            current_label="Actual",
        )
    elif ctx.comparison is not None and ctx.comparison_period is not None:
        steps = operating_income_bridge(
            ctx.current,
            ctx.comparison,
            base_label=ctx.comparison_period.label,
            current_label=ctx.period.label,
        )
    else:
        return BridgeResponse(
            filters=ctx.applied_filters(),
            basis=basis,
            available=False,
            base_label=None,
            current_label=None,
            total_change=None,
            steps=[],
        )
    return BridgeResponse(
        filters=ctx.applied_filters(),
        basis=basis,
        available=True,
        base_label=steps[0].label,
        current_label=steps[-1].label,
        total_change=money(steps[-1].amount - steps[0].amount),
        steps=[
            BridgeStepItem(key=s.key, label=s.label, kind=s.kind, amount=money(s.amount))
            for s in steps
        ],
    )


# --------------------------------------------------------------------------- #
# Price - volume - mix
# --------------------------------------------------------------------------- #
PVM_ITEM = ["business_unit_code", "product_code"]


def pvm_effects(ctx: AnalysisContext) -> pd.DataFrame | None:
    """Price-volume-mix effects per business unit x product, with descriptive columns.

    The item is the product *within a business unit* because the same product sells at a
    different price in each channel; mixing channels would report channel mix as price.
    """
    if ctx.sales_comparison is None:
        return None
    current = ctx.sales_current.groupby(PVM_ITEM, observed=True)[["units", "net_revenue"]].sum()
    base = ctx.sales_comparison.groupby(PVM_ITEM, observed=True)[["units", "net_revenue"]].sum()
    effects = price_volume_mix(current, base)
    effects.index = effects.index.set_names(PVM_ITEM)

    descriptors = (
        pd.concat([ctx.sales_current, ctx.sales_comparison])
        .drop_duplicates(PVM_ITEM)
        .set_index(PVM_ITEM)[["business_unit_name", "category_code", "category_name"]]
    )
    return effects.join(descriptors).reset_index()


def _pvm_row(key: str, label: str, values: pd.Series) -> PvmRow:
    return PvmRow(
        key=key,
        label=label,
        base_revenue=money(values["base_revenue"]),
        current_revenue=money(values["current_revenue"]),
        volume_effect=money(values["volume_effect"]),
        mix_effect=money(values["mix_effect"]),
        price_effect=money(values["price_effect"]),
        total_change=money(values["current_revenue"] - values["base_revenue"]),
    )


def price_volume_mix_analysis(ctx: AnalysisContext, group_by: str) -> PvmResponse:
    effects = pvm_effects(ctx)
    if effects is None:
        return PvmResponse(
            filters=ctx.applied_filters(),
            group_by=group_by,
            available=False,
            rows=[],
            total=None,
        )
    key_column, label_column = SEGMENTS[group_by]
    measures = ["base_revenue", "current_revenue", *PVM_COLUMNS]
    grouped = effects.groupby([key_column, label_column], observed=True)[measures].sum()
    grouped = grouped.sort_values("current_revenue", ascending=False)
    return PvmResponse(
        filters=ctx.applied_filters(),
        group_by=group_by,
        available=True,
        rows=[_pvm_row(key, label, values) for (key, label), values in grouped.iterrows()],
        total=_pvm_row("total", "Total", effects[measures].sum()),
    )


# --------------------------------------------------------------------------- #
# Gross margin drivers (mix vs rate)
# --------------------------------------------------------------------------- #
def _segment_frame(sales: pd.DataFrame, key_column: str) -> pd.DataFrame:
    grouped = sales.groupby(key_column, observed=True)[["net_revenue", "direct_costs"]].sum()
    grouped["gross_profit"] = grouped["net_revenue"] - grouped["direct_costs"]
    return grouped


def margin_drivers(ctx: AnalysisContext, group_by: str) -> MarginDriversResponse:
    key_column, label_column = SEGMENTS[group_by]
    if ctx.sales_comparison is None:
        return MarginDriversResponse(
            filters=ctx.applied_filters(),
            group_by=group_by,
            available=False,
            base_margin=None,
            current_margin=None,
            margin_change=None,
            rate_effect=None,
            mix_effect=None,
            rows=[],
        )
    current = _segment_frame(ctx.sales_current, key_column)
    base = _segment_frame(ctx.sales_comparison, key_column)
    effects = margin_mix_rate(current, base)
    labels = (
        pd.concat([ctx.sales_current, ctx.sales_comparison])
        .drop_duplicates(key_column)
        .set_index(key_column)[label_column]
    )
    current_margin = safe_ratio(current["gross_profit"].sum(), current["net_revenue"].sum())
    base_margin = safe_ratio(base["gross_profit"].sum(), base["net_revenue"].sum())
    ordered = effects.assign(total=effects["rate_effect"] + effects["mix_effect"]).sort_values(
        "total"
    )
    return MarginDriversResponse(
        filters=ctx.applied_filters(),
        group_by=group_by,
        available=True,
        base_margin=ratio(base_margin),
        current_margin=ratio(current_margin),
        margin_change=(
            ratio(current_margin - base_margin)
            if current_margin is not None and base_margin is not None
            else None
        ),
        rate_effect=ratio(effects["rate_effect"].sum()),
        mix_effect=ratio(effects["mix_effect"].sum()),
        rows=[
            MarginDriverRow(
                key=str(key),
                label=str(labels.get(key, key)),
                base_share=ratio(row.base_share),
                current_share=ratio(row.current_share),
                base_margin=ratio(row.base_margin),
                current_margin=ratio(row.current_margin),
                rate_effect=ratio(row.rate_effect) or 0.0,
                mix_effect=ratio(row.mix_effect) or 0.0,
                total_effect=ratio(row.total) or 0.0,
            )
            for key, row in zip(ordered.index, ordered.itertuples(index=False), strict=True)
        ],
    )


# --------------------------------------------------------------------------- #
# Anomalies
# --------------------------------------------------------------------------- #
def anomalies_in_period(ctx: AnalysisContext) -> pd.DataFrame:
    """Anomalies scored on the whole history, restricted to the selected period."""
    return ctx.period.select(anomaly_model.detect_anomalies(ctx.history))


def anomaly_item(row: pd.Series) -> Anomaly:
    return Anomaly(
        month=month_key(row["month"]),
        business_unit_code=row["business_unit_code"],
        business_unit_name=row["business_unit_name"],
        account_code=row["account_code"],
        account_name=row["account_name"],
        account_type=row["account_type"],
        actual=money(row["actual"]),
        budget=money(row["budget"]),
        variance=money(row["variance"]),
        variance_pct=round(float(row["variance_pct"]), 6),
        typical_variance_pct=round(float(row["typical_variance_pct"]), 6),
        robust_z=round(float(row["robust_z"]), 2),
        status=favorability(
            row["variance"], row["budget"], higher_is_better=row["account_type"] == REVENUE
        ),
        is_material=bool(row["is_material"]),
        materiality_threshold=money(row["materiality_threshold"]),
    )


def anomalies(ctx: AnalysisContext, include_immaterial: bool) -> AnomaliesResponse:
    found = anomalies_in_period(ctx)
    if not include_immaterial:
        found = found[found["is_material"]]
    series = ctx.history[ctx.history["budget"] > 0].groupby(
        ["business_unit_code", "account_code"], observed=True
    )
    return AnomaliesResponse(
        filters=ctx.applied_filters(),
        method=AnomalyMethod(
            signal="Monthly budget variance % per business unit x account",
            score="Modified z-score: 0.6745 x (variance % - median) / MAD, over the full history",
            z_threshold=anomaly_model.Z_THRESHOLD,
            materiality=(
                f"|variance| >= {anomaly_model.MATERIALITY_SHARE_OF_REVENUE:.1%} of the business "
                "unit's average monthly net revenue"
            ),
            series_evaluated=series.ngroups,
            months_of_history=ctx.available.n_months,
        ),
        anomalies=[anomaly_item(row) for _, row in found.iterrows()],
    )
