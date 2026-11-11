"""create star schema and etl audit tables

Revision ID: 0001
Revises: None
Create Date: 2026-11-11 16:56:12.491664
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('dim_account',
    sa.Column('account_key', sa.SmallInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('account_code', sa.String(length=4), nullable=False),
    sa.Column('account_name', sa.String(length=60), nullable=False),
    sa.Column('account_type', sa.String(length=20), nullable=False),
    sa.Column('account_group', sa.String(length=40), nullable=False),
    sa.Column('cost_behavior', sa.String(length=20), nullable=False),
    sa.Column('statement_order', sa.SmallInteger(), nullable=False),
    sa.CheckConstraint("account_type IN ('REVENUE', 'DIRECT_COST', 'OPERATING_EXPENSE')", name=op.f('ck_dim_account_account_type_valid')),
    sa.CheckConstraint("cost_behavior IN ('VARIABLE', 'FIXED', 'SEMI_VARIABLE', 'DISCRETIONARY', 'NOT_APPLICABLE')", name=op.f('ck_dim_account_cost_behavior_valid')),
    sa.PrimaryKeyConstraint('account_key', name=op.f('pk_dim_account')),
    sa.UniqueConstraint('account_code', name=op.f('uq_dim_account_account_code'))
    )
    op.create_table('dim_business_unit',
    sa.Column('business_unit_key', sa.SmallInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('business_unit_code', sa.String(length=3), nullable=False),
    sa.Column('business_unit_name', sa.String(length=60), nullable=False),
    sa.Column('sales_channel', sa.String(length=40), nullable=False),
    sa.PrimaryKeyConstraint('business_unit_key', name=op.f('pk_dim_business_unit')),
    sa.UniqueConstraint('business_unit_code', name=op.f('uq_dim_business_unit_business_unit_code'))
    )
    op.create_table('dim_cost_center',
    sa.Column('cost_center_key', sa.SmallInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('cost_center_code', sa.String(length=3), nullable=False),
    sa.Column('cost_center_name', sa.String(length=60), nullable=False),
    sa.Column('function_area', sa.String(length=40), nullable=False),
    sa.PrimaryKeyConstraint('cost_center_key', name=op.f('pk_dim_cost_center')),
    sa.UniqueConstraint('cost_center_code', name=op.f('uq_dim_cost_center_cost_center_code'))
    )
    op.create_table('dim_date',
    sa.Column('date_key', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('full_date', sa.Date(), nullable=False),
    sa.Column('year', sa.SmallInteger(), nullable=False),
    sa.Column('quarter', sa.SmallInteger(), nullable=False),
    sa.Column('quarter_label', sa.String(length=7), nullable=False),
    sa.Column('month', sa.SmallInteger(), nullable=False),
    sa.Column('month_name', sa.String(length=9), nullable=False),
    sa.Column('month_short', sa.String(length=3), nullable=False),
    sa.Column('year_month', sa.String(length=7), nullable=False),
    sa.Column('month_start_date', sa.Date(), nullable=False),
    sa.Column('month_start_key', sa.Integer(), nullable=False),
    sa.Column('day_of_month', sa.SmallInteger(), nullable=False),
    sa.Column('day_of_week', sa.SmallInteger(), nullable=False),
    sa.Column('day_name', sa.String(length=9), nullable=False),
    sa.Column('is_weekend', sa.Boolean(), nullable=False),
    sa.Column('is_month_start', sa.Boolean(), nullable=False),
    sa.CheckConstraint('date_key = (EXTRACT(YEAR FROM full_date) * 10000 + EXTRACT(MONTH FROM full_date) * 100 + EXTRACT(DAY FROM full_date))::int', name=op.f('ck_dim_date_key_matches_date')),
    sa.CheckConstraint('day_of_week BETWEEN 1 AND 7', name=op.f('ck_dim_date_day_of_week_range')),
    sa.CheckConstraint('month BETWEEN 1 AND 12', name=op.f('ck_dim_date_month_range')),
    sa.CheckConstraint('quarter BETWEEN 1 AND 4', name=op.f('ck_dim_date_quarter_range')),
    sa.PrimaryKeyConstraint('date_key', name=op.f('pk_dim_date')),
    sa.UniqueConstraint('full_date', name=op.f('uq_dim_date_full_date'))
    )
    op.create_index(op.f('ix_dim_date_month_start_key'), 'dim_date', ['month_start_key'], unique=False)
    op.create_index(op.f('ix_dim_date_year_month'), 'dim_date', ['year_month'], unique=False)
    op.create_table('dim_product',
    sa.Column('product_key', sa.Integer(), sa.Identity(always=False), nullable=False),
    sa.Column('product_code', sa.String(length=7), nullable=False),
    sa.Column('product_name', sa.String(length=80), nullable=False),
    sa.Column('category_code', sa.String(length=3), nullable=False),
    sa.Column('category_name', sa.String(length=40), nullable=False),
    sa.Column('list_price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('standard_unit_cost', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.CheckConstraint('list_price > 0', name=op.f('ck_dim_product_list_price_positive')),
    sa.CheckConstraint('standard_unit_cost > 0', name=op.f('ck_dim_product_unit_cost_positive')),
    sa.PrimaryKeyConstraint('product_key', name=op.f('pk_dim_product')),
    sa.UniqueConstraint('product_code', name=op.f('uq_dim_product_product_code'))
    )
    op.create_index('ix_dim_product_category_code', 'dim_product', ['category_code'], unique=False)
    op.create_table('etl_run',
    sa.Column('run_id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('source_seed', sa.BigInteger(), nullable=True),
    sa.Column('generator_version', sa.String(length=20), nullable=True),
    sa.Column('data_period_start', sa.Date(), nullable=True),
    sa.Column('data_period_end', sa.Date(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.CheckConstraint("status IN ('RUNNING', 'SUCCESS', 'FAILED')", name=op.f('ck_etl_run_status_valid')),
    sa.PrimaryKeyConstraint('run_id', name=op.f('pk_etl_run'))
    )
    op.create_table('etl_data_quality_check',
    sa.Column('check_id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('run_id', sa.BigInteger(), nullable=False),
    sa.Column('check_code', sa.String(length=40), nullable=False),
    sa.Column('check_name', sa.String(length=120), nullable=False),
    sa.Column('dataset', sa.String(length=40), nullable=False),
    sa.Column('quality_dimension', sa.String(length=20), nullable=False),
    sa.Column('stage', sa.String(length=20), nullable=False),
    sa.Column('severity', sa.String(length=10), nullable=False),
    sa.Column('status', sa.String(length=4), nullable=False),
    sa.Column('rows_checked', sa.Integer(), nullable=False),
    sa.Column('rows_failed', sa.Integer(), nullable=False),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.CheckConstraint("severity IN ('ERROR', 'WARNING')", name=op.f('ck_etl_data_quality_check_severity_valid')),
    sa.CheckConstraint("status IN ('PASS', 'WARN', 'FAIL')", name=op.f('ck_etl_data_quality_check_status_valid')),
    sa.ForeignKeyConstraint(['run_id'], ['etl_run.run_id'], name=op.f('fk_etl_data_quality_check_run_id'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('check_id', name=op.f('pk_etl_data_quality_check'))
    )
    op.create_index(op.f('ix_etl_data_quality_check_run_id'), 'etl_data_quality_check', ['run_id'], unique=False)
    op.create_table('etl_table_load',
    sa.Column('run_id', sa.BigInteger(), nullable=False),
    sa.Column('target_table', sa.String(length=40), nullable=False),
    sa.Column('source_file', sa.String(length=60), nullable=False),
    sa.Column('rows_read', sa.Integer(), nullable=False),
    sa.Column('rows_standardized', sa.Integer(), nullable=False),
    sa.Column('rows_rejected', sa.Integer(), nullable=False),
    sa.Column('rows_deduplicated', sa.Integer(), nullable=False),
    sa.Column('rows_loaded', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['etl_run.run_id'], name=op.f('fk_etl_table_load_run_id'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('run_id', 'target_table', name=op.f('pk_etl_table_load'))
    )
    op.create_table('fact_budget',
    sa.Column('month_date_key', sa.Integer(), nullable=False),
    sa.Column('business_unit_key', sa.SmallInteger(), nullable=False),
    sa.Column('account_key', sa.SmallInteger(), nullable=False),
    sa.Column('budget_amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.CheckConstraint('budget_amount >= 0', name=op.f('ck_fact_budget_amount_non_negative')),
    sa.CheckConstraint('MOD(month_date_key, 100) = 1', name=op.f('ck_fact_budget_month_key_is_first_day')),
    sa.ForeignKeyConstraint(['account_key'], ['dim_account.account_key'], name=op.f('fk_fact_budget_account_key')),
    sa.ForeignKeyConstraint(['business_unit_key'], ['dim_business_unit.business_unit_key'], name=op.f('fk_fact_budget_business_unit_key')),
    sa.ForeignKeyConstraint(['month_date_key'], ['dim_date.date_key'], name=op.f('fk_fact_budget_month_date_key')),
    sa.PrimaryKeyConstraint('month_date_key', 'business_unit_key', 'account_key', name=op.f('pk_fact_budget'))
    )
    op.create_index('ix_fact_budget_business_unit_account', 'fact_budget', ['business_unit_key', 'account_key'], unique=False)
    op.create_table('fact_operating_expenses',
    sa.Column('entry_id', sa.String(length=11), nullable=False),
    sa.Column('date_key', sa.Integer(), nullable=False),
    sa.Column('business_unit_key', sa.SmallInteger(), nullable=False),
    sa.Column('cost_center_key', sa.SmallInteger(), nullable=False),
    sa.Column('account_key', sa.SmallInteger(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.CheckConstraint('amount > 0', name=op.f('ck_fact_operating_expenses_amount_positive')),
    sa.ForeignKeyConstraint(['account_key'], ['dim_account.account_key'], name=op.f('fk_fact_operating_expenses_account_key')),
    sa.ForeignKeyConstraint(['business_unit_key'], ['dim_business_unit.business_unit_key'], name=op.f('fk_fact_operating_expenses_business_unit_key')),
    sa.ForeignKeyConstraint(['cost_center_key'], ['dim_cost_center.cost_center_key'], name=op.f('fk_fact_operating_expenses_cost_center_key')),
    sa.ForeignKeyConstraint(['date_key'], ['dim_date.date_key'], name=op.f('fk_fact_operating_expenses_date_key')),
    sa.PrimaryKeyConstraint('entry_id', name=op.f('pk_fact_operating_expenses'))
    )
    op.create_index('ix_fact_operating_expenses_account', 'fact_operating_expenses', ['account_key'], unique=False)
    op.create_index('ix_fact_operating_expenses_cost_center', 'fact_operating_expenses', ['cost_center_key'], unique=False)
    op.create_index('ix_fact_operating_expenses_date_business_unit', 'fact_operating_expenses', ['date_key', 'business_unit_key'], unique=False)
    op.create_table('fact_sales',
    sa.Column('date_key', sa.Integer(), nullable=False),
    sa.Column('business_unit_key', sa.SmallInteger(), nullable=False),
    sa.Column('product_key', sa.Integer(), nullable=False),
    sa.Column('units_sold', sa.Integer(), nullable=False),
    sa.Column('gross_sales_amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('discount_amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('net_sales_amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('cogs_amount', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.CheckConstraint('cogs_amount >= 0', name=op.f('ck_fact_sales_cogs_non_negative')),
    sa.CheckConstraint('discount_amount >= 0', name=op.f('ck_fact_sales_discount_non_negative')),
    sa.CheckConstraint('gross_sales_amount >= 0', name=op.f('ck_fact_sales_gross_non_negative')),
    sa.CheckConstraint('net_sales_amount = gross_sales_amount - discount_amount', name=op.f('ck_fact_sales_net_identity')),
    sa.CheckConstraint('units_sold > 0', name=op.f('ck_fact_sales_units_positive')),
    sa.ForeignKeyConstraint(['business_unit_key'], ['dim_business_unit.business_unit_key'], name=op.f('fk_fact_sales_business_unit_key')),
    sa.ForeignKeyConstraint(['date_key'], ['dim_date.date_key'], name=op.f('fk_fact_sales_date_key')),
    sa.ForeignKeyConstraint(['product_key'], ['dim_product.product_key'], name=op.f('fk_fact_sales_product_key')),
    sa.PrimaryKeyConstraint('date_key', 'business_unit_key', 'product_key', name=op.f('pk_fact_sales'))
    )
    op.create_index('ix_fact_sales_business_unit_date', 'fact_sales', ['business_unit_key', 'date_key'], unique=False)
    op.create_index('ix_fact_sales_product_date', 'fact_sales', ['product_key', 'date_key'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_fact_sales_product_date', table_name='fact_sales')
    op.drop_index('ix_fact_sales_business_unit_date', table_name='fact_sales')
    op.drop_table('fact_sales')
    op.drop_index('ix_fact_operating_expenses_date_business_unit', table_name='fact_operating_expenses')
    op.drop_index('ix_fact_operating_expenses_cost_center', table_name='fact_operating_expenses')
    op.drop_index('ix_fact_operating_expenses_account', table_name='fact_operating_expenses')
    op.drop_table('fact_operating_expenses')
    op.drop_index('ix_fact_budget_business_unit_account', table_name='fact_budget')
    op.drop_table('fact_budget')
    op.drop_table('etl_table_load')
    op.drop_index(op.f('ix_etl_data_quality_check_run_id'), table_name='etl_data_quality_check')
    op.drop_table('etl_data_quality_check')
    op.drop_table('etl_run')
    op.drop_index('ix_dim_product_category_code', table_name='dim_product')
    op.drop_table('dim_product')
    op.drop_index(op.f('ix_dim_date_year_month'), table_name='dim_date')
    op.drop_index(op.f('ix_dim_date_month_start_key'), table_name='dim_date')
    op.drop_table('dim_date')
    op.drop_table('dim_cost_center')
    op.drop_table('dim_business_unit')
    op.drop_table('dim_account')
