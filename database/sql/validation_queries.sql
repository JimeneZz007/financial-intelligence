-- Independent validation queries for the star schema.
--
-- Every query returns the rows that VIOLATE a rule, so a healthy warehouse returns zero
-- rows for all of them. They are written separately from the ETL code on purpose: they
-- verify the result, not the process.
--
-- Run them with:  scripts/run_validation_queries.sh
-- They also run in the automated test suite (tests/integration/test_validation_sql.py).

-- name: fact_sales_grain_is_unique
SELECT date_key, business_unit_key, product_key, COUNT(*) AS row_count
FROM fact_sales
GROUP BY date_key, business_unit_key, product_key
HAVING COUNT(*) > 1;

-- name: fact_budget_grain_is_unique
SELECT month_date_key, business_unit_key, account_key, COUNT(*) AS row_count
FROM fact_budget
GROUP BY month_date_key, business_unit_key, account_key
HAVING COUNT(*) > 1;

-- name: fact_sales_net_equals_gross_minus_discount
SELECT date_key, business_unit_key, product_key
FROM fact_sales
WHERE net_sales_amount <> gross_sales_amount - discount_amount;

-- name: fact_sales_has_no_orphan_keys
SELECT s.date_key, s.business_unit_key, s.product_key
FROM fact_sales s
LEFT JOIN dim_date d ON d.date_key = s.date_key
LEFT JOIN dim_business_unit b ON b.business_unit_key = s.business_unit_key
LEFT JOIN dim_product p ON p.product_key = s.product_key
WHERE d.date_key IS NULL OR b.business_unit_key IS NULL OR p.product_key IS NULL;

-- name: fact_operating_expenses_has_no_orphan_keys
SELECT e.entry_id
FROM fact_operating_expenses e
LEFT JOIN dim_date d ON d.date_key = e.date_key
LEFT JOIN dim_business_unit b ON b.business_unit_key = e.business_unit_key
LEFT JOIN dim_cost_center c ON c.cost_center_key = e.cost_center_key
LEFT JOIN dim_account a ON a.account_key = e.account_key
WHERE d.date_key IS NULL OR b.business_unit_key IS NULL
   OR c.cost_center_key IS NULL OR a.account_key IS NULL;

-- name: fact_budget_has_no_orphan_keys
SELECT f.month_date_key, f.business_unit_key, f.account_key
FROM fact_budget f
LEFT JOIN dim_date d ON d.date_key = f.month_date_key
LEFT JOIN dim_business_unit b ON b.business_unit_key = f.business_unit_key
LEFT JOIN dim_account a ON a.account_key = f.account_key
WHERE d.date_key IS NULL OR b.business_unit_key IS NULL OR a.account_key IS NULL;

-- name: fact_budget_month_key_is_first_day_of_month
SELECT f.month_date_key
FROM fact_budget f
JOIN dim_date d ON d.date_key = f.month_date_key
WHERE NOT d.is_month_start;

-- name: operating_expenses_use_only_operating_accounts
SELECT e.entry_id, a.account_code, a.account_type
FROM fact_operating_expenses e
JOIN dim_account a ON a.account_key = e.account_key
WHERE a.account_type <> 'OPERATING_EXPENSE';

-- name: budget_grid_is_complete
-- Every month x business unit x account must have a budget line.
SELECT m.month_start_key, b.business_unit_code, a.account_code
FROM (SELECT DISTINCT month_start_key FROM dim_date) m
CROSS JOIN dim_business_unit b
CROSS JOIN dim_account a
LEFT JOIN fact_budget f
  ON  f.month_date_key = m.month_start_key
  AND f.business_unit_key = b.business_unit_key
  AND f.account_key = a.account_key
WHERE f.month_date_key IS NULL;

-- name: dim_date_has_no_gaps
SELECT expected.day::date AS missing_date
FROM generate_series(
       (SELECT MIN(full_date) FROM dim_date),
       (SELECT MAX(full_date) FROM dim_date),
       INTERVAL '1 day'
     ) AS expected(day)
LEFT JOIN dim_date d ON d.full_date = expected.day::date
WHERE d.date_key IS NULL;

-- name: dim_date_covers_whole_months
SELECT year_month, COUNT(*) AS days_loaded
FROM dim_date
GROUP BY year_month, month_start_date
HAVING COUNT(*) <> EXTRACT(DAY FROM (month_start_date + INTERVAL '1 month - 1 day'));

-- name: category_code_maps_to_one_name
SELECT category_code, COUNT(DISTINCT category_name) AS names
FROM dim_product
GROUP BY category_code
HAVING COUNT(DISTINCT category_name) > 1;

-- name: every_business_unit_sells_every_month
SELECT m.year_month, b.business_unit_code
FROM (SELECT DISTINCT year_month FROM dim_date) m
CROSS JOIN dim_business_unit b
LEFT JOIN (
    SELECT DISTINCT d.year_month, s.business_unit_key
    FROM fact_sales s
    JOIN dim_date d ON d.date_key = s.date_key
) sold ON sold.year_month = m.year_month AND sold.business_unit_key = b.business_unit_key
WHERE sold.business_unit_key IS NULL;

-- name: actuals_view_reconciles_with_facts
-- The drill-across view must carry exactly the totals of the underlying facts.
WITH view_totals AS (
    SELECT a.account_type, SUM(v.actual_amount) AS total
    FROM vw_actual_by_account_month v
    JOIN dim_account a ON a.account_key = v.account_key
    GROUP BY a.account_type
),
fact_totals AS (
    SELECT 'REVENUE' AS account_type, SUM(net_sales_amount) AS total FROM fact_sales
    UNION ALL
    SELECT 'DIRECT_COST', SUM(cogs_amount) FROM fact_sales
    UNION ALL
    SELECT 'OPERATING_EXPENSE', SUM(amount) FROM fact_operating_expenses
)
SELECT f.account_type, f.total AS fact_total, v.total AS view_total
FROM fact_totals f
LEFT JOIN view_totals v ON v.account_type = f.account_type
WHERE v.total IS DISTINCT FROM f.total;

-- name: comparison_view_grain_is_unique
SELECT month_date_key, business_unit_key, account_key, COUNT(*) AS row_count
FROM vw_budget_vs_actual
GROUP BY month_date_key, business_unit_key, account_key
HAVING COUNT(*) > 1;

-- name: no_product_sells_below_cost_overall
SELECT p.product_code, SUM(s.net_sales_amount) AS net_sales, SUM(s.cogs_amount) AS cogs
FROM fact_sales s
JOIN dim_product p ON p.product_key = s.product_key
GROUP BY p.product_code
HAVING SUM(s.cogs_amount) >= SUM(s.net_sales_amount);
