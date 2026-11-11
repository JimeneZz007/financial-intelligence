"""Business scenarios injected into the synthetic data.

A scenario is a documented deviation from the baseline plan (a lost customer, a freight
rate spike...). Each one declares:

* its *effects*: the levers the generator moves, and
* its *signatures*: the footprint it is expected to leave on budget variance, used as
  ground truth when evaluating the anomaly detector (scripts/evaluate_anomaly_detection.py).

The analytics layer never reads this module: findings shown in the product are computed
from the loaded data only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from pipelines.generate.config import BU_CODES, COGS_ACCOUNT, REVENUE_ACCOUNT

# Accounts that move mechanically with sales volume.
VOLUME_DRIVEN_ACCOUNTS: tuple[str, ...] = (COGS_ACCOUNT, "6400", "6800")


def month_range(first: str, last: str) -> tuple[str, ...]:
    """Inclusive range of 'YYYY-MM' keys."""
    year, month = (int(part) for part in first.split("-"))
    keys: list[str] = []
    while True:
        key = f"{year:04d}-{month:02d}"
        keys.append(key)
        if key == last:
            return tuple(keys)
        month += 1
        if month == 13:
            year, month = year + 1, 1


@dataclass(frozen=True)
class Effect:
    """A lever moved by the generator.

    lever:
        DEMAND            multiplier on expected units sold
        UNIT_COST         multiplier on supplier unit cost (per category)
        LIST_PRICE        multiplier on list price (per category)
        OPEX_MULTIPLIER   multiplier on an operating-expense account
        OPEX_ADDITION     fixed monthly amount added to an operating-expense account
    """

    lever: str
    business_units: tuple[str, ...]
    months: dict[str, float]  # 'YYYY-MM' -> multiplier or amount
    account_code: str | None = None
    category_code: str | None = None
    budgeted_from_year: int | None = None  # year whose budget already includes the effect


@dataclass(frozen=True)
class Signature:
    """Expected footprint on budget variance for (account, business unit, month) cells."""

    account_code: str
    business_units: tuple[str, ...]
    months: tuple[str, ...]
    direction: str  # FAVORABLE | UNFAVORABLE
    role: str  # PRIMARY (direct effect) | DERIVED (mechanical consequence)


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    description: str
    effects: tuple[Effect, ...]
    signatures: tuple[Signature, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _volume_signatures(
    business_units: tuple[str, ...], months: tuple[str, ...], revenue_direction: str
) -> tuple[Signature, ...]:
    """Revenue signature plus the volume-driven cost accounts moving the opposite way."""
    cost_direction = "UNFAVORABLE" if revenue_direction == "FAVORABLE" else "FAVORABLE"
    derived = tuple(
        Signature(account, business_units, months, cost_direction, "DERIVED")
        for account in VOLUME_DRIVEN_ACCOUNTS
    )
    return (
        Signature(REVENUE_ACCOUNT, business_units, months, revenue_direction, "PRIMARY"),
        *derived,
    )


_S1_CORE = month_range("2024-04", "2024-06")
_S1_TAIL = month_range("2024-07", "2024-08")
_S2 = month_range("2025-03", "2025-04")
_S4 = month_range("2025-07", "2025-12")
_S5 = month_range("2025-01", "2025-12")
_S5_PRICE = month_range("2025-07", "2025-12")
_S6 = month_range("2024-08", "2024-11")
_S8_ALL = month_range("2024-03", "2025-12")
_S8_UNBUDGETED = month_range("2024-03", "2024-12")
_S9 = month_range("2024-10", "2024-12")

SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        id="S1",
        name="Wholesale key-account loss",
        description=(
            "A major distributor stops ordering from Wholesale Distribution in April 2024. "
            "Demand falls 26% for three months and recovers gradually by September."
        ),
        effects=(
            Effect(
                "DEMAND",
                ("WHS",),
                {**dict.fromkeys(_S1_CORE, 0.74), **dict.fromkeys(_S1_TAIL, 0.92)},
            ),
        ),
        signatures=(
            *_volume_signatures(("WHS",), _S1_CORE, "UNFAVORABLE"),
            Signature(REVENUE_ACCOUNT, ("WHS",), _S1_TAIL, "UNFAVORABLE", "DERIVED"),
        ),
    ),
    Scenario(
        id="S2",
        name="E-commerce acquisition campaign",
        description=(
            "E-commerce runs an unbudgeted acquisition campaign in March-April 2025. "
            "Advertising spend rises 85% and 35% over its baseline while demand rises "
            "14% and 10%."
        ),
        effects=(
            Effect("OPEX_MULTIPLIER", ("ECM",), {"2025-03": 1.85, "2025-04": 1.35}, "6200"),
            Effect("DEMAND", ("ECM",), {"2025-03": 1.14, "2025-04": 1.10}),
        ),
        signatures=(
            Signature("6200", ("ECM",), _S2, "UNFAVORABLE", "PRIMARY"),
            Signature(REVENUE_ACCOUNT, ("ECM",), _S2, "FAVORABLE", "PRIMARY"),
            *(
                Signature(account, ("ECM",), _S2, "UNFAVORABLE", "DERIVED")
                for account in VOLUME_DRIVEN_ACCOUNTS
            ),
        ),
    ),
    Scenario(
        id="S3",
        name="Retail flagship store renovation",
        description=(
            "The flagship store closes partially for renovation in February 2025; "
            "Retail Stores demand drops 20% that month."
        ),
        effects=(Effect("DEMAND", ("RET",), {"2025-02": 0.80}),),
        signatures=_volume_signatures(("RET",), ("2025-02",), "UNFAVORABLE"),
    ),
    Scenario(
        id="S4",
        name="Corporate supply contract win",
        description=(
            "Corporate Solutions signs a new supply contract effective July 2025, "
            "lifting demand 28% for the rest of the year. Not in the 2025 budget."
        ),
        effects=(Effect("DEMAND", ("COR",), dict.fromkeys(_S4, 1.28)),),
        signatures=_volume_signatures(("COR",), _S4, "FAVORABLE"),
    ),
    Scenario(
        id="S5",
        name="Electronics supplier cost increase",
        description=(
            "Electronics suppliers raise unit costs 7% from January 2025 on top of normal "
            "inflation. The company answers with a 4% list-price increase in July 2025. "
            "Neither was in the 2025 budget."
        ),
        effects=(
            Effect("UNIT_COST", BU_CODES, dict.fromkeys(_S5, 1.07), category_code="ELE"),
            Effect("LIST_PRICE", BU_CODES, dict.fromkeys(_S5_PRICE, 1.04), category_code="ELE"),
        ),
        signatures=(
            Signature(COGS_ACCOUNT, BU_CODES, _S5, "UNFAVORABLE", "PRIMARY"),
            Signature(REVENUE_ACCOUNT, BU_CODES, _S5_PRICE, "FAVORABLE", "DERIVED"),
            Signature("6800", BU_CODES, _S5_PRICE, "UNFAVORABLE", "DERIVED"),
            Signature("6400", BU_CODES, _S5_PRICE, "UNFAVORABLE", "DERIVED"),
        ),
    ),
    Scenario(
        id="S6",
        name="Freight rate spike",
        description=(
            "Carrier rates rise 38% between August and November 2024 for every business unit."
        ),
        effects=(Effect("OPEX_MULTIPLIER", BU_CODES, dict.fromkeys(_S6, 1.38), "6400"),),
        signatures=(Signature("6400", BU_CODES, _S6, "UNFAVORABLE", "PRIMARY"),),
    ),
    Scenario(
        id="S7",
        name="Retail legal settlement",
        description=(
            "Retail Stores books a one-off USD 185,000 legal settlement under Professional "
            "Services in September 2023."
        ),
        effects=(Effect("OPEX_ADDITION", ("RET",), {"2023-09": 185_000.0}, "6600"),),
        signatures=(Signature("6600", ("RET",), ("2023-09",), "UNFAVORABLE", "PRIMARY"),),
    ),
    Scenario(
        id="S8",
        name="E-commerce platform migration",
        description=(
            "E-commerce migrates to a new commerce platform in March 2024, adding "
            "USD 22,000 per month of software cost. Unbudgeted in 2024, included in the "
            "2025 budget."
        ),
        effects=(
            Effect(
                "OPEX_ADDITION",
                ("ECM",),
                dict.fromkeys(_S8_ALL, 22_000.0),
                "6500",
                budgeted_from_year=2025,
            ),
        ),
        signatures=(Signature("6500", ("ECM",), _S8_UNBUDGETED, "UNFAVORABLE", "PRIMARY"),),
    ),
    Scenario(
        id="S9",
        name="Travel freeze",
        description=(
            "Wholesale Distribution and Corporate Solutions freeze non-essential travel in "
            "the fourth quarter of 2024; travel spend falls 60%."
        ),
        effects=(Effect("OPEX_MULTIPLIER", ("WHS", "COR"), dict.fromkeys(_S9, 0.40), "6700"),),
        signatures=(Signature("6700", ("WHS", "COR"), _S9, "FAVORABLE", "PRIMARY"),),
    ),
)


def effects_by_lever(lever: str) -> list[Effect]:
    return [
        effect for scenario in SCENARIOS for effect in scenario.effects if effect.lever == lever
    ]
