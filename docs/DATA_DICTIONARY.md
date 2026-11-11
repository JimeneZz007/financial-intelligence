# Diccionario de datos

Describe los extractos de origen y las tablas del almacén. Todos los importes están en USD.
Los datos son sintéticos ([DATA_GENERATION.md](DATA_GENERATION.md)).

## 1. Extractos de origen (`data/synthetic/`)

Archivos CSV en UTF-8 con encabezado. Llegan como texto y pueden contener los defectos
descritos en [DATA_QUALITY.md](DATA_QUALITY.md).

### `sales_transactions.csv`

| Columna | Tipo esperado | Descripción |
|---------|---------------|-------------|
| `transaction_date` | fecha `AAAA-MM-DD` | Día de la venta |
| `business_unit_code` | texto (3) | Código de la unidad de negocio |
| `product_code` | texto (7) | Código del producto |
| `units_sold` | entero > 0 | Unidades vendidas en el día |
| `gross_sales_amount` | decimal ≥ 0 | Venta a precio realizado antes de descuentos |
| `discount_amount` | decimal ≥ 0 | Descuentos concedidos |
| `net_sales_amount` | decimal | Venta neta = bruta − descuento |
| `cogs_amount` | decimal ≥ 0 | Costo de la mercancía vendida |

### `expense_ledger.csv`

| Columna | Tipo esperado | Descripción |
|---------|---------------|-------------|
| `entry_id` | texto (11) | Identificador único del asiento (`EXP-0000001`) |
| `posting_date` | fecha `AAAA-MM-DD` | Fecha de contabilización |
| `business_unit_code` | texto (3) | Unidad de negocio que asume el gasto |
| `cost_center_code` | texto (3) | Centro de costo |
| `account_code` | texto (4) | Cuenta de gasto operativo (`6xxx`) |
| `amount` | decimal > 0 | Importe del asiento |

### `budget_plan.csv`

| Columna | Tipo esperado | Descripción |
|---------|---------------|-------------|
| `fiscal_year` | entero | Año fiscal (calendario) |
| `fiscal_month` | entero 1–12 | Mes |
| `business_unit_code` | texto (3) | Unidad de negocio |
| `account_code` | texto (4) | Cuenta presupuestada (ingresos, costo de ventas o gasto) |
| `budget_amount` | decimal ≥ 0 | Importe presupuestado del mes |

### Datos maestros

| Archivo | Columnas |
|---------|----------|
| `business_units.csv` | `business_unit_code`, `business_unit_name`, `sales_channel` |
| `products.csv` | `product_code`, `product_name`, `category_code`, `category_name`, `list_price`, `standard_unit_cost` |
| `cost_centers.csv` | `cost_center_code`, `cost_center_name`, `function_area` |
| `chart_of_accounts.csv` | `account_code`, `account_name`, `account_type`, `account_group`, `cost_behavior`, `statement_order` |

## 2. Dimensiones

### `dim_date` — un día por fila

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `date_key` | `integer` PK | Fecha como `AAAAMMDD` |
| `full_date` | `date` UNIQUE | Fecha calendario |
| `year` | `smallint` | Año |
| `quarter` | `smallint` | Trimestre (1–4) |
| `quarter_label` | `varchar(7)` | Etiqueta `2024-Q1` |
| `month` | `smallint` | Mes (1–12) |
| `month_name` | `varchar(9)` | Nombre del mes en inglés |
| `month_short` | `varchar(3)` | Abreviatura del mes |
| `year_month` | `varchar(7)` | Etiqueta `2024-03` |
| `month_start_date` | `date` | Primer día del mes |
| `month_start_key` | `integer` | `date_key` del primer día del mes; lleva hechos diarios al grano mensual |
| `day_of_month` | `smallint` | Día del mes |
| `day_of_week` | `smallint` | Día ISO (1 = lunes … 7 = domingo) |
| `day_name` | `varchar(9)` | Nombre del día en inglés |
| `is_weekend` | `boolean` | Sábado o domingo |
| `is_month_start` | `boolean` | Primer día del mes |

### `dim_business_unit`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `business_unit_key` | `smallint` PK | Clave sustituta |
| `business_unit_code` | `varchar(3)` UNIQUE | Clave natural (`RET`, `ECM`, `WHS`, `COR`) |
| `business_unit_name` | `varchar(60)` | Nombre |
| `sales_channel` | `varchar(40)` | Canal comercial |

### `dim_product`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `product_key` | `integer` PK | Clave sustituta |
| `product_code` | `varchar(7)` UNIQUE | Clave natural (`ELE-001`) |
| `product_name` | `varchar(80)` | Nombre |
| `category_code` | `varchar(3)` | Código de categoría (`ELE`, `OFF`, `FUR`, `HOM`, `ACC`) |
| `category_name` | `varchar(40)` | Nombre de la categoría |
| `list_price` | `numeric(10,2)` | Precio de lista del año base |
| `standard_unit_cost` | `numeric(10,2)` | Costo unitario estándar del año base |

`list_price` y `standard_unit_cost` son atributos descriptivos del año base; no se usan para
calcular indicadores, que parten siempre de los importes de `fact_sales`.

### `dim_cost_center`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `cost_center_key` | `smallint` PK | Clave sustituta |
| `cost_center_code` | `varchar(3)` UNIQUE | Clave natural (`SAL`, `MKT`, `LOG`, `ADM`, `TEC`, `HRS`) |
| `cost_center_name` | `varchar(60)` | Nombre |
| `function_area` | `varchar(40)` | Área funcional (`Commercial`, `Operations`, `Support`) |

### `dim_account`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `account_key` | `smallint` PK | Clave sustituta |
| `account_code` | `varchar(4)` UNIQUE | Clave natural |
| `account_name` | `varchar(60)` | Nombre de la cuenta |
| `account_type` | `varchar(20)` | `REVENUE`, `DIRECT_COST` u `OPERATING_EXPENSE` |
| `account_group` | `varchar(40)` | Agrupación para análisis (Personnel, Marketing, Occupancy…) |
| `cost_behavior` | `varchar(20)` | `FIXED`, `VARIABLE`, `SEMI_VARIABLE`, `DISCRETIONARY` o `NOT_APPLICABLE` |
| `statement_order` | `smallint` | Orden de presentación en el estado de resultados |

**Plan de cuentas**

| Código | Cuenta | Tipo | Grupo | Comportamiento |
|--------|--------|------|-------|----------------|
| 4000 | Net Sales Revenue | REVENUE | Revenue | — |
| 5000 | Cost of Goods Sold | DIRECT_COST | Cost of Sales | VARIABLE |
| 6100 | Salaries & Wages | OPERATING_EXPENSE | Personnel | FIXED |
| 6150 | Employee Benefits | OPERATING_EXPENSE | Personnel | FIXED |
| 6200 | Advertising & Promotion | OPERATING_EXPENSE | Marketing | DISCRETIONARY |
| 6300 | Rent & Occupancy | OPERATING_EXPENSE | Occupancy | FIXED |
| 6350 | Utilities | OPERATING_EXPENSE | Occupancy | SEMI_VARIABLE |
| 6400 | Freight & Distribution | OPERATING_EXPENSE | Logistics | VARIABLE |
| 6500 | Software & IT Services | OPERATING_EXPENSE | Technology | FIXED |
| 6600 | Professional Services | OPERATING_EXPENSE | General & Administrative | DISCRETIONARY |
| 6700 | Travel & Entertainment | OPERATING_EXPENSE | General & Administrative | DISCRETIONARY |
| 6800 | Payment Processing Fees | OPERATING_EXPENSE | Selling | VARIABLE |
| 6900 | Depreciation & Amortization | OPERATING_EXPENSE | Depreciation | FIXED |

## 3. Hechos

### `fact_sales` — día × unidad de negocio × producto

| Columna | Tipo | Aditiva | Descripción |
|---------|------|:-------:|-------------|
| `date_key` | `integer` PK, FK | — | Día de la venta |
| `business_unit_key` | `smallint` PK, FK | — | Unidad de negocio |
| `product_key` | `integer` PK, FK | — | Producto |
| `units_sold` | `integer` | Sí | Unidades vendidas (> 0) |
| `gross_sales_amount` | `numeric(14,2)` | Sí | Venta bruta |
| `discount_amount` | `numeric(14,2)` | Sí | Descuentos |
| `net_sales_amount` | `numeric(14,2)` | Sí | Venta neta = bruta − descuento |
| `cogs_amount` | `numeric(14,2)` | Sí | Costo de la mercancía vendida |

### `fact_operating_expenses` — asiento de gasto

| Columna | Tipo | Aditiva | Descripción |
|---------|------|:-------:|-------------|
| `entry_id` | `varchar(11)` PK | — | Identificador del asiento en el libro (dimensión degenerada) |
| `date_key` | `integer` FK | — | Fecha de contabilización |
| `business_unit_key` | `smallint` FK | — | Unidad de negocio |
| `cost_center_key` | `smallint` FK | — | Centro de costo |
| `account_key` | `smallint` FK | — | Cuenta de gasto operativo |
| `amount` | `numeric(14,2)` | Sí | Importe del asiento (> 0) |

### `fact_budget` — mes × unidad de negocio × cuenta

| Columna | Tipo | Aditiva | Descripción |
|---------|------|:-------:|-------------|
| `month_date_key` | `integer` PK, FK | — | Primer día del mes presupuestado |
| `business_unit_key` | `smallint` PK, FK | — | Unidad de negocio |
| `account_key` | `smallint` PK, FK | — | Cuenta presupuestada |
| `budget_amount` | `numeric(14,2)` | Sí* | Importe presupuestado (≥ 0) |

\* Aditiva dentro de un mismo tipo de cuenta. Sumar presupuesto de ingresos con presupuesto
de gastos no tiene significado financiero; los indicadores siempre separan por
`account_type`.

## 4. Vistas

### `vw_actual_by_account_month`

| Columna | Descripción |
|---------|-------------|
| `month_date_key` | Primer día del mes |
| `business_unit_key` | Unidad de negocio |
| `account_key` | Cuenta (`4000` ingresos, `5000` costo de ventas, `6xxx` gastos) |
| `actual_amount` | Ejecución del mes |

### `vw_budget_vs_actual`

| Columna | Descripción |
|---------|-------------|
| `month_date_key`, `business_unit_key`, `account_key` | Grano de la comparación |
| `budget_amount` | Presupuesto (0 si no existe) |
| `actual_amount` | Ejecución (0 si no existe) |
| `has_budget`, `has_actual` | Indican si la celda existe en cada lado |

## 5. Auditoría del ETL

### `etl_run`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `run_id` | `bigint` PK | Identificador de la ejecución |
| `started_at`, `finished_at` | `timestamptz` | Inicio y fin |
| `status` | `varchar(10)` | `RUNNING`, `SUCCESS` o `FAILED` |
| `source_seed` | `bigint` | Semilla declarada en el manifiesto de origen |
| `generator_version` | `varchar(20)` | Versión del generador |
| `data_period_start`, `data_period_end` | `date` | Periodo cubierto por los datos cargados |
| `error_message` | `text` | Motivo del fallo, si lo hubo |

### `etl_table_load`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `run_id`, `target_table` | PK | Ejecución y tabla de destino |
| `source_file` | `varchar(60)` | Extracto de origen |
| `rows_read` | `integer` | Filas leídas del extracto |
| `rows_standardized` | `integer` | Filas corregidas por estandarización |
| `rows_rejected` | `integer` | Filas apartadas por incumplir una regla |
| `rows_deduplicated` | `integer` | Duplicados exactos eliminados |
| `rows_loaded` | `integer` | Filas cargadas en la tabla |

Se cumple siempre `rows_read = rows_rejected + rows_deduplicated + rows_loaded`.

### `etl_data_quality_check`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `check_id` | `bigint` PK | Identificador |
| `run_id` | `bigint` FK | Ejecución |
| `check_code` | `varchar(40)` | Código estable de la regla |
| `check_name` | `varchar(120)` | Descripción breve |
| `dataset` | `varchar(40)` | Extracto o tabla evaluada |
| `quality_dimension` | `varchar(20)` | Dimensión de calidad (completitud, validez, unicidad…) |
| `stage` | `varchar(20)` | `SOURCE` (extracto) o `WAREHOUSE` (después de cargar) |
| `severity` | `varchar(10)` | `ERROR` detiene la carga; `WARNING` solo informa |
| `status` | `varchar(4)` | `PASS`, `WARN` o `FAIL` |
| `rows_checked`, `rows_failed` | `integer` | Filas evaluadas y filas que incumplen |
| `details` | `jsonb` | Valores observados y esperados |
