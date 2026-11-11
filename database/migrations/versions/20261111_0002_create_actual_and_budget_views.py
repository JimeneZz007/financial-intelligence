"""create actual and budget comparison views

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-11

The three fact tables have different grains. These views bring actuals to the grain of
the budget (month x business unit x account) so both can be compared without double
counting:

* revenue actuals  = fact_sales.net_sales_amount, mapped to account 4000
* direct costs     = fact_sales.cogs_amount, mapped to account 5000
* operating costs  = fact_operating_expenses.amount, by its own account (6xxx)
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTUAL_VIEW = """
CREATE VIEW vw_actual_by_account_month AS
SELECT d.month_start_key AS month_date_key,
       s.business_unit_key,
       a.account_key,
       SUM(s.net_sales_amount) AS actual_amount
FROM fact_sales s
JOIN dim_date d ON d.date_key = s.date_key
JOIN dim_account a ON a.account_code = '4000'
GROUP BY d.month_start_key, s.business_unit_key, a.account_key
UNION ALL
SELECT d.month_start_key,
       s.business_unit_key,
       a.account_key,
       SUM(s.cogs_amount)
FROM fact_sales s
JOIN dim_date d ON d.date_key = s.date_key
JOIN dim_account a ON a.account_code = '5000'
GROUP BY d.month_start_key, s.business_unit_key, a.account_key
UNION ALL
SELECT d.month_start_key,
       e.business_unit_key,
       e.account_key,
       SUM(e.amount)
FROM fact_operating_expenses e
JOIN dim_date d ON d.date_key = e.date_key
GROUP BY d.month_start_key, e.business_unit_key, e.account_key
"""

BUDGET_VS_ACTUAL_VIEW = """
CREATE VIEW vw_budget_vs_actual AS
SELECT COALESCE(b.month_date_key, a.month_date_key)       AS month_date_key,
       COALESCE(b.business_unit_key, a.business_unit_key) AS business_unit_key,
       COALESCE(b.account_key, a.account_key)             AS account_key,
       COALESCE(b.budget_amount, 0)                       AS budget_amount,
       COALESCE(a.actual_amount, 0)                       AS actual_amount,
       b.budget_amount IS NOT NULL                        AS has_budget,
       a.actual_amount IS NOT NULL                        AS has_actual
FROM fact_budget b
FULL OUTER JOIN vw_actual_by_account_month a
  ON  a.month_date_key = b.month_date_key
  AND a.business_unit_key = b.business_unit_key
  AND a.account_key = b.account_key
"""


def upgrade() -> None:
    op.execute(ACTUAL_VIEW)
    op.execute(BUDGET_VS_ACTUAL_VIEW)


def downgrade() -> None:
    op.execute("DROP VIEW vw_budget_vs_actual")
    op.execute("DROP VIEW vw_actual_by_account_month")
