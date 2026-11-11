"""Dimensional model (star schema) and ETL audit tables.

Grain of each fact table:

* fact_sales                one row per calendar day x business unit x product
* fact_operating_expenses   one row per expense ledger entry
* fact_budget               one row per month x business unit x account

Monetary columns are NUMERIC(14, 2) in USD. See docs/DATA_MODEL.md.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "pk": "pk_%(table_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
}

Money = Numeric(14, 2)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# --------------------------------------------------------------------------- #
# Dimensions
# --------------------------------------------------------------------------- #
class DimDate(Base):
    """Calendar dimension, one row per day. The key is the date as YYYYMMDD."""

    __tablename__ = "dim_date"
    __table_args__ = (
        CheckConstraint("month BETWEEN 1 AND 12", name="month_range"),
        CheckConstraint("quarter BETWEEN 1 AND 4", name="quarter_range"),
        CheckConstraint("day_of_week BETWEEN 1 AND 7", name="day_of_week_range"),
        CheckConstraint(
            "date_key = (EXTRACT(YEAR FROM full_date) * 10000"
            " + EXTRACT(MONTH FROM full_date) * 100 + EXTRACT(DAY FROM full_date))::int",
            name="key_matches_date",
        ),
    )

    date_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    full_date: Mapped[date] = mapped_column(Date, unique=True)
    year: Mapped[int] = mapped_column(SmallInteger)
    quarter: Mapped[int] = mapped_column(SmallInteger)
    quarter_label: Mapped[str] = mapped_column(String(7))  # 2024-Q1
    month: Mapped[int] = mapped_column(SmallInteger)
    month_name: Mapped[str] = mapped_column(String(9))
    month_short: Mapped[str] = mapped_column(String(3))
    year_month: Mapped[str] = mapped_column(String(7), index=True)  # 2024-03
    month_start_date: Mapped[date] = mapped_column(Date)
    month_start_key: Mapped[int] = mapped_column(Integer, index=True)
    day_of_month: Mapped[int] = mapped_column(SmallInteger)
    day_of_week: Mapped[int] = mapped_column(SmallInteger)  # 1 = Monday (ISO)
    day_name: Mapped[str] = mapped_column(String(9))
    is_weekend: Mapped[bool] = mapped_column(Boolean)
    is_month_start: Mapped[bool] = mapped_column(Boolean)


class DimBusinessUnit(Base):
    __tablename__ = "dim_business_unit"

    business_unit_key: Mapped[int] = mapped_column(SmallInteger, Identity(), primary_key=True)
    business_unit_code: Mapped[str] = mapped_column(String(3), unique=True)
    business_unit_name: Mapped[str] = mapped_column(String(60))
    sales_channel: Mapped[str] = mapped_column(String(40))


class DimProduct(Base):
    """Product dimension. The category hierarchy is denormalised here (see D-005)."""

    __tablename__ = "dim_product"
    __table_args__ = (
        CheckConstraint("list_price > 0", name="list_price_positive"),
        CheckConstraint("standard_unit_cost > 0", name="unit_cost_positive"),
        Index("ix_dim_product_category_code", "category_code"),
    )

    product_key: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    product_code: Mapped[str] = mapped_column(String(7), unique=True)
    product_name: Mapped[str] = mapped_column(String(80))
    category_code: Mapped[str] = mapped_column(String(3))
    category_name: Mapped[str] = mapped_column(String(40))
    list_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    standard_unit_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2))


class DimCostCenter(Base):
    __tablename__ = "dim_cost_center"

    cost_center_key: Mapped[int] = mapped_column(SmallInteger, Identity(), primary_key=True)
    cost_center_code: Mapped[str] = mapped_column(String(3), unique=True)
    cost_center_name: Mapped[str] = mapped_column(String(60))
    function_area: Mapped[str] = mapped_column(String(40))


class DimAccount(Base):
    __tablename__ = "dim_account"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('REVENUE', 'DIRECT_COST', 'OPERATING_EXPENSE')",
            name="account_type_valid",
        ),
        CheckConstraint(
            "cost_behavior IN ('VARIABLE', 'FIXED', 'SEMI_VARIABLE', 'DISCRETIONARY',"
            " 'NOT_APPLICABLE')",
            name="cost_behavior_valid",
        ),
    )

    account_key: Mapped[int] = mapped_column(SmallInteger, Identity(), primary_key=True)
    account_code: Mapped[str] = mapped_column(String(4), unique=True)
    account_name: Mapped[str] = mapped_column(String(60))
    account_type: Mapped[str] = mapped_column(String(20))
    account_group: Mapped[str] = mapped_column(String(40))
    cost_behavior: Mapped[str] = mapped_column(String(20))
    statement_order: Mapped[int] = mapped_column(SmallInteger)


# --------------------------------------------------------------------------- #
# Facts
# --------------------------------------------------------------------------- #
class FactSales(Base):
    """Grain: one row per calendar day x business unit x product."""

    __tablename__ = "fact_sales"
    __table_args__ = (
        CheckConstraint("units_sold > 0", name="units_positive"),
        CheckConstraint("gross_sales_amount >= 0", name="gross_non_negative"),
        CheckConstraint("discount_amount >= 0", name="discount_non_negative"),
        CheckConstraint("cogs_amount >= 0", name="cogs_non_negative"),
        CheckConstraint(
            "net_sales_amount = gross_sales_amount - discount_amount", name="net_identity"
        ),
        # The primary key leads with date_key; these support unit- and product-led access.
        Index("ix_fact_sales_business_unit_date", "business_unit_key", "date_key"),
        Index("ix_fact_sales_product_date", "product_key", "date_key"),
    )

    date_key: Mapped[int] = mapped_column(ForeignKey("dim_date.date_key"), primary_key=True)
    business_unit_key: Mapped[int] = mapped_column(
        ForeignKey("dim_business_unit.business_unit_key"), primary_key=True
    )
    product_key: Mapped[int] = mapped_column(
        ForeignKey("dim_product.product_key"), primary_key=True
    )
    units_sold: Mapped[int] = mapped_column(Integer)
    gross_sales_amount: Mapped[Decimal] = mapped_column(Money)
    discount_amount: Mapped[Decimal] = mapped_column(Money)
    net_sales_amount: Mapped[Decimal] = mapped_column(Money)
    cogs_amount: Mapped[Decimal] = mapped_column(Money)


class FactOperatingExpense(Base):
    """Grain: one row per expense ledger entry (entry_id is a degenerate dimension)."""

    __tablename__ = "fact_operating_expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_fact_operating_expenses_date_business_unit", "date_key", "business_unit_key"),
        Index("ix_fact_operating_expenses_account", "account_key"),
        Index("ix_fact_operating_expenses_cost_center", "cost_center_key"),
    )

    entry_id: Mapped[str] = mapped_column(String(11), primary_key=True)
    date_key: Mapped[int] = mapped_column(ForeignKey("dim_date.date_key"))
    business_unit_key: Mapped[int] = mapped_column(
        ForeignKey("dim_business_unit.business_unit_key")
    )
    cost_center_key: Mapped[int] = mapped_column(ForeignKey("dim_cost_center.cost_center_key"))
    account_key: Mapped[int] = mapped_column(ForeignKey("dim_account.account_key"))
    amount: Mapped[Decimal] = mapped_column(Money)


class FactBudget(Base):
    """Grain: one row per month x business unit x account.

    month_date_key references the first day of the month in dim_date.
    """

    __tablename__ = "fact_budget"
    __table_args__ = (
        CheckConstraint("MOD(month_date_key, 100) = 1", name="month_key_is_first_day"),
        CheckConstraint("budget_amount >= 0", name="amount_non_negative"),
        Index("ix_fact_budget_business_unit_account", "business_unit_key", "account_key"),
    )

    month_date_key: Mapped[int] = mapped_column(ForeignKey("dim_date.date_key"), primary_key=True)
    business_unit_key: Mapped[int] = mapped_column(
        ForeignKey("dim_business_unit.business_unit_key"), primary_key=True
    )
    account_key: Mapped[int] = mapped_column(
        ForeignKey("dim_account.account_key"), primary_key=True
    )
    budget_amount: Mapped[Decimal] = mapped_column(Money)


# --------------------------------------------------------------------------- #
# ETL audit
# --------------------------------------------------------------------------- #
class EtlRun(Base):
    """One row per execution of the ETL pipeline."""

    __tablename__ = "etl_run"
    __table_args__ = (
        CheckConstraint("status IN ('RUNNING', 'SUCCESS', 'FAILED')", name="status_valid"),
    )

    run_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(10))
    source_seed: Mapped[int | None] = mapped_column(BigInteger)
    generator_version: Mapped[str | None] = mapped_column(String(20))
    data_period_start: Mapped[date | None] = mapped_column(Date)
    data_period_end: Mapped[date | None] = mapped_column(Date)
    error_message: Mapped[str | None] = mapped_column(Text)


class EtlTableLoad(Base):
    """Row accounting per source extract for a run: read, rejected, deduplicated, loaded."""

    __tablename__ = "etl_table_load"

    run_id: Mapped[int] = mapped_column(
        ForeignKey("etl_run.run_id", ondelete="CASCADE"), primary_key=True
    )
    target_table: Mapped[str] = mapped_column(String(40), primary_key=True)
    source_file: Mapped[str] = mapped_column(String(60))
    rows_read: Mapped[int] = mapped_column(Integer)
    rows_standardized: Mapped[int] = mapped_column(Integer)
    rows_rejected: Mapped[int] = mapped_column(Integer)
    rows_deduplicated: Mapped[int] = mapped_column(Integer)
    rows_loaded: Mapped[int] = mapped_column(Integer)


class EtlDataQualityCheck(Base):
    """Result of one data-quality rule in a run."""

    __tablename__ = "etl_data_quality_check"
    __table_args__ = (
        CheckConstraint("status IN ('PASS', 'WARN', 'FAIL')", name="status_valid"),
        CheckConstraint("severity IN ('ERROR', 'WARNING')", name="severity_valid"),
    )

    check_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("etl_run.run_id", ondelete="CASCADE"), index=True
    )
    check_code: Mapped[str] = mapped_column(String(40))
    check_name: Mapped[str] = mapped_column(String(120))
    dataset: Mapped[str] = mapped_column(String(40))
    quality_dimension: Mapped[str] = mapped_column(String(20))
    stage: Mapped[str] = mapped_column(String(20))  # SOURCE | WAREHOUSE
    severity: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(4))
    rows_checked: Mapped[int] = mapped_column(Integer)
    rows_failed: Mapped[int] = mapped_column(Integer)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
