"""API test fixtures: a client bound to the test database and an independent oracle."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from backend.app.db.session import get_session
from backend.app.main import app
from pipelines.generate.dataset import Dataset

API = "/api/v1"


@pytest.fixture(scope="session")
def client(loaded_engine: Engine) -> Iterator[TestClient]:
    def override_session() -> Iterator[Session]:
        with Session(loaded_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@dataclass(frozen=True)
class Oracle:
    """Recomputes figures with pandas straight from the generator's clean frames.

    It shares no code with the API (no SQL, no views, no analytics module), so agreement
    between both is evidence that the numbers are right, not that one bug was copied.
    """

    sales: pd.DataFrame
    ledger: pd.DataFrame
    budget: pd.DataFrame

    @staticmethod
    def _slice(frame: pd.DataFrame, start: str, end: str, units: list[str] | None) -> pd.DataFrame:
        selected = frame[(frame["month"] >= start) & (frame["month"] <= end)]
        if units:
            selected = selected[selected["business_unit_code"].isin(units)]
        return selected

    def actual(self, start: str, end: str, units: list[str] | None = None) -> dict[str, float]:
        sales = self._slice(self.sales, start, end, units)
        ledger = self._slice(self.ledger, start, end, units)
        revenue = float(sales["net_sales_amount"].sum())
        cogs = float(sales["cogs_amount"].sum())
        opex = float(ledger["amount"].sum())
        return self._statement(revenue, cogs, opex)

    def planned(self, start: str, end: str, units: list[str] | None = None) -> dict[str, float]:
        budget = self._slice(self.budget, start, end, units)
        by_account = budget.groupby("account_code")["budget_amount"].sum()
        revenue = float(by_account.get("4000", 0.0))
        cogs = float(by_account.get("5000", 0.0))
        opex = float(by_account.drop(["4000", "5000"], errors="ignore").sum())
        return self._statement(revenue, cogs, opex)

    @staticmethod
    def _statement(revenue: float, cogs: float, opex: float) -> dict[str, float]:
        return {
            "net_revenue": revenue,
            "direct_costs": cogs,
            "gross_profit": revenue - cogs,
            "gross_margin": (revenue - cogs) / revenue,
            "operating_expenses": opex,
            "operating_income": revenue - cogs - opex,
            "operating_margin": (revenue - cogs - opex) / revenue,
        }


@pytest.fixture(scope="session")
def oracle(dataset: Dataset) -> Oracle:
    sales = dataset.clean["sales_transactions"].assign(
        month=lambda f: f["transaction_date"].str.slice(0, 7),
        category_code=lambda f: f["product_code"].str.slice(0, 3),
    )
    ledger = dataset.clean["expense_ledger"].assign(
        month=lambda f: f["posting_date"].str.slice(0, 7)
    )
    budget = dataset.clean["budget_plan"].assign(
        month=lambda f: (
            f["fiscal_year"].astype(str) + "-" + f["fiscal_month"].astype(str).str.zfill(2)
        ),
        account_code=lambda f: f["account_code"].astype(str),
    )
    return Oracle(sales=sales, ledger=ledger, budget=budget)
