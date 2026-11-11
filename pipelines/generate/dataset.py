"""Builds the complete synthetic dataset and writes the raw extracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pipelines.generate import config as cfg
from pipelines.generate import defects
from pipelines.generate.budget import generate_budget
from pipelines.generate.expenses import actual_monthly_opex, generate_expense_ledger
from pipelines.generate.sales import (
    actual_monthly_revenue,
    build_demand_model,
    generate_sales,
    monthly_by_unit,
    product_unit_costs,
)
from pipelines.generate.scenarios import SCENARIOS
from pipelines.generate.timeline import build_timeline

MANIFEST_NAME = "MANIFEST.json"
SCENARIOS_NAME = "scenarios.json"

_MONEY_COLUMNS = {
    "sales_transactions": [
        "gross_sales_amount",
        "discount_amount",
        "net_sales_amount",
        "cogs_amount",
    ],
    "expense_ledger": ["amount"],
    "budget_plan": ["budget_amount"],
    "products": ["list_price", "standard_unit_cost"],
}


@dataclass(frozen=True)
class Dataset:
    """Clean frames (typed) and raw frames (strings, with injected defects)."""

    clean: dict[str, pd.DataFrame]
    raw: dict[str, pd.DataFrame]
    control_totals: dict[str, Any]


def _master_data(unit_costs: np.ndarray) -> dict[str, pd.DataFrame]:
    return {
        "business_units": pd.DataFrame(
            [(bu.code, bu.name, bu.channel) for bu in cfg.BUSINESS_UNITS],
            columns=["business_unit_code", "business_unit_name", "sales_channel"],
        ),
        "products": pd.DataFrame(
            [
                (
                    p.code,
                    p.name,
                    p.category_code,
                    cfg.CATEGORY_BY_CODE[p.category_code].name,
                    p.list_price,
                    float(cost),
                )
                for p, cost in zip(cfg.PRODUCTS, unit_costs, strict=True)
            ],
            columns=[
                "product_code",
                "product_name",
                "category_code",
                "category_name",
                "list_price",
                "standard_unit_cost",
            ],
        ),
        "cost_centers": pd.DataFrame([asdict(cc) for cc in cfg.COST_CENTERS]).rename(
            columns={"code": "cost_center_code", "name": "cost_center_name"}
        ),
        "chart_of_accounts": pd.DataFrame([asdict(a) for a in cfg.ACCOUNTS]).rename(
            columns={"code": "account_code", "name": "account_name"}
        ),
    }


def _as_text(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Render a typed frame exactly as it is written to CSV (two-decimal amounts)."""
    text = frame.copy()
    for column in _MONEY_COLUMNS.get(name, []):
        text[column] = text[column].map("{:.2f}".format)
    return text.astype(str)


def _control_totals(clean: dict[str, pd.DataFrame]) -> dict[str, Any]:
    sales, ledger, budget = (
        clean["sales_transactions"],
        clean["expense_ledger"],
        clean["budget_plan"],
    )
    return {
        "sales_transactions": {
            "rows": len(sales),
            "units_sold": int(sales["units_sold"].sum()),
            "gross_sales_amount": round(float(sales["gross_sales_amount"].sum()), 2),
            "discount_amount": round(float(sales["discount_amount"].sum()), 2),
            "net_sales_amount": round(float(sales["net_sales_amount"].sum()), 2),
            "cogs_amount": round(float(sales["cogs_amount"].sum()), 2),
        },
        "expense_ledger": {
            "rows": len(ledger),
            "amount": round(float(ledger["amount"].sum()), 2),
        },
        "budget_plan": {
            "rows": len(budget),
            "budget_amount": round(float(budget["budget_amount"].sum()), 2),
        },
    }


def build_dataset(seed: int = cfg.SEED) -> Dataset:
    # Independent random streams: changing one component never shifts the others.
    streams = np.random.SeedSequence(seed).spawn(4)
    rng_products, rng_sales, rng_expenses, rng_defects = (
        np.random.default_rng(stream) for stream in streams
    )

    timeline = build_timeline(cfg.PERIOD_START, cfg.PERIOD_END)
    unit_costs = product_unit_costs(rng_products)
    model = build_demand_model(timeline, unit_costs)

    sales = generate_sales(timeline, model, rng_sales)
    monthly_opex = actual_monthly_opex(
        timeline,
        plan_revenue=monthly_by_unit(timeline, model.plan_net_revenue),
        actual_revenue=actual_monthly_revenue(timeline, sales),
        rng=rng_expenses,
    )
    ledger = generate_expense_ledger(timeline, monthly_opex, rng_expenses)
    budget = generate_budget(timeline, model)

    clean = {
        **_master_data(unit_costs),
        "sales_transactions": sales,
        "expense_ledger": ledger,
        "budget_plan": budget,
    }
    raw = {name: _as_text(name, frame) for name, frame in clean.items()}
    raw["sales_transactions"] = defects.inject_sales_defects(raw["sales_transactions"], rng_defects)
    raw["expense_ledger"] = defects.inject_expense_defects(raw["expense_ledger"], rng_defects)
    raw["budget_plan"] = defects.inject_budget_defects(raw["budget_plan"], rng_defects)
    return Dataset(clean=clean, raw=raw, control_totals=_control_totals(clean))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_dataset(dataset: Dataset, out_dir: Path, seed: int = cfg.SEED) -> dict[str, Any]:
    """Write CSV extracts, the scenario ground truth and the manifest. Returns the manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, dict[str, Any]] = {}
    for name, frame in dataset.raw.items():
        path = out_dir / f"{name}.csv"
        frame.to_csv(path, index=False, lineterminator="\n")
        files[path.name] = {"rows": len(frame), "sha256": _sha256(path)}

    scenarios_path = out_dir / SCENARIOS_NAME
    scenarios_path.write_text(
        json.dumps([s.to_dict() for s in SCENARIOS], indent=2) + "\n", encoding="utf-8"
    )

    manifest = {
        "generator_version": cfg.GENERATOR_VERSION,
        "seed": seed,
        "company": cfg.COMPANY_NAME,
        "synthetic": True,
        "currency": cfg.CURRENCY,
        "period": {"start": cfg.PERIOD_START.isoformat(), "end": cfg.PERIOD_END.isoformat()},
        "files": files,
        "control_totals": dataset.control_totals,
        "injected_defects": {
            "sales_transactions": defects.SALES_DEFECTS,
            "expense_ledger": defects.EXPENSE_DEFECTS,
            "budget_plan": defects.BUDGET_DEFECTS,
        },
    }
    (out_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
