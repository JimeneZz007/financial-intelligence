// FINANCIAL INTELLIGENCE - Power Query (M) for the star schema
//
// One query per table. Create each one in Power BI Desktop with
//   Home > Get data > Blank query > Advanced Editor
// and name it exactly as indicated in the comment above it.
//
// Source: the CSV files exported by the pipeline (`make powerbi-data`), in powerbi/data/.
// First create a text parameter named DataFolder with the full path of that folder,
// ending in a backslash, for example  C:\repos\financial-intelligence\powerbi\data\
//
// To read from PostgreSQL instead, replace the Source step of each query with the one
// shown at the end of this file. Types are then taken from the database.

// ---------------------------------------------------------------------------
// Helper function - name: fnReadCsv
// ---------------------------------------------------------------------------
(fileName as text) as table =>
let
    Source = Csv.Document(
        File.Contents(DataFolder & fileName),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
in
    Promoted

// ---------------------------------------------------------------------------
// name: dim_date
// ---------------------------------------------------------------------------
let
    Source = fnReadCsv("dim_date.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"date_key", Int64.Type},
            {"full_date", type date},
            {"year", Int64.Type},
            {"quarter", Int64.Type},
            {"quarter_label", type text},
            {"month", Int64.Type},
            {"month_name", type text},
            {"month_short", type text},
            {"year_month", type text},
            {"month_start_date", type date},
            {"month_start_key", Int64.Type},
            {"day_of_month", Int64.Type},
            {"day_of_week", Int64.Type},
            {"day_name", type text},
            {"is_weekend", type logical},
            {"is_month_start", type logical}
        },
        "en-US"
    )
in
    Typed

// ---------------------------------------------------------------------------
// name: dim_business_unit
// ---------------------------------------------------------------------------
let
    Source = fnReadCsv("dim_business_unit.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"business_unit_key", Int64.Type},
            {"business_unit_code", type text},
            {"business_unit_name", type text},
            {"sales_channel", type text}
        }
    )
in
    Typed

// ---------------------------------------------------------------------------
// name: dim_product
// ---------------------------------------------------------------------------
let
    Source = fnReadCsv("dim_product.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"product_key", Int64.Type},
            {"product_code", type text},
            {"product_name", type text},
            {"category_code", type text},
            {"category_name", type text},
            {"list_price", Currency.Type},
            {"standard_unit_cost", Currency.Type}
        },
        "en-US"
    )
in
    Typed

// ---------------------------------------------------------------------------
// name: dim_cost_center
// ---------------------------------------------------------------------------
let
    Source = fnReadCsv("dim_cost_center.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"cost_center_key", Int64.Type},
            {"cost_center_code", type text},
            {"cost_center_name", type text},
            {"function_area", type text}
        }
    )
in
    Typed

// ---------------------------------------------------------------------------
// name: dim_account
// ---------------------------------------------------------------------------
let
    Source = fnReadCsv("dim_account.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"account_key", Int64.Type},
            {"account_code", type text},
            {"account_name", type text},
            {"account_type", type text},
            {"account_group", type text},
            {"cost_behavior", type text},
            {"statement_order", Int64.Type}
        }
    )
in
    Typed

// ---------------------------------------------------------------------------
// name: fact_sales
// Grain: one row per day x business unit x product
// ---------------------------------------------------------------------------
let
    Source = fnReadCsv("fact_sales.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"date_key", Int64.Type},
            {"business_unit_key", Int64.Type},
            {"product_key", Int64.Type},
            {"units_sold", Int64.Type},
            {"gross_sales_amount", Currency.Type},
            {"discount_amount", Currency.Type},
            {"net_sales_amount", Currency.Type},
            {"cogs_amount", Currency.Type}
        },
        "en-US"
    )
in
    Typed

// ---------------------------------------------------------------------------
// name: fact_operating_expenses
// Grain: one row per expense ledger entry
// ---------------------------------------------------------------------------
let
    Source = fnReadCsv("fact_operating_expenses.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"entry_id", type text},
            {"date_key", Int64.Type},
            {"business_unit_key", Int64.Type},
            {"cost_center_key", Int64.Type},
            {"account_key", Int64.Type},
            {"amount", Currency.Type}
        },
        "en-US"
    )
in
    Typed

// ---------------------------------------------------------------------------
// name: fact_budget
// Grain: one row per month x business unit x account.
// month_date_key is the date_key of the first day of the month.
// ---------------------------------------------------------------------------
let
    Source = fnReadCsv("fact_budget.csv"),
    Typed = Table.TransformColumnTypes(
        Source,
        {
            {"month_date_key", Int64.Type},
            {"business_unit_key", Int64.Type},
            {"account_key", Int64.Type},
            {"budget_amount", Currency.Type}
        },
        "en-US"
    )
in
    Typed

// ---------------------------------------------------------------------------
// Alternative source: PostgreSQL
// ---------------------------------------------------------------------------
// Replace the Source step of a query with (example for fact_sales):
//
//   Source = PostgreSQL.Database("HOST:5433", "financial_intelligence"),
//   Table  = Source{[Schema = "public", Item = "fact_sales"]}[Data]
//
// and remove the Typed step. The database must be reachable from the Windows machine
// running Power BI Desktop, and the Npgsql provider must be installed.
