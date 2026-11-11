# Calidad de datos

La calidad se controla en tres niveles independientes: reglas del pipeline, restricciones de
la base de datos y consultas SQL de validación. Los resultados de cada ejecución se guardan
en la base de datos y se muestran en la vista **Data Quality** de la aplicación.

## 1. Semántica de los resultados

| Estado | Significado |
|--------|-------------|
| `PASS` | La regla se cumple en todas las filas |
| `WARN` | Se encontró un problema y el pipeline lo resolvió: reparó, deduplicó o apartó las filas. La carga continúa |
| `FAIL` | La regla no se cumple y no hay resolución automática |

| Severidad | Efecto de un `FAIL` |
|-----------|---------------------|
| `ERROR` | Detiene la ejecución y revierte la carga |
| `WARNING` | Solo informa |

**Tolerancia de rechazo.** Apartar filas inválidas es aceptable mientras sean pocas. Si las
filas rechazadas de un extracto superan el **1 %**, la regla `*_REJECT_RATE` falla y la
carga se detiene: un rechazo masivo indica un problema en el origen, no filas sueltas
defectuosas.

## 2. Reglas del pipeline

### 2.1 Extractos de origen (`stage = SOURCE`)

| Código | Dimensión | Regla | Acción si falla |
|--------|-----------|-------|-----------------|
| `SALES_STANDARDISED` | Consistencia | Códigos sin espacios y en mayúsculas | Reparar |
| `SALES_REQUIRED_FIELDS` | Completitud | Ningún campo vacío | Cuarentena |
| `SALES_VALID_DATE` | Validez | Fecha calendario válida | Cuarentena |
| `SALES_VALID_AMOUNTS` | Validez | Unidades enteras > 0; importes numéricos ≥ 0 | Cuarentena |
| `SALES_KNOWN_BUSINESS_UNIT` | Integridad | La unidad existe en datos maestros | Cuarentena |
| `SALES_KNOWN_PRODUCT` | Integridad | El producto existe en datos maestros | Cuarentena |
| `SALES_NET_IDENTITY` | Consistencia | Neta = bruta − descuento | Cuarentena |
| `SALES_EXACT_DUPLICATES` | Unicidad | Sin filas duplicadas exactas | Deduplicar |
| `SALES_GRAIN_UNIQUE` | Unicidad | Fecha × unidad × producto es único | **Detener** |
| `EXPENSES_STANDARDISED` | Consistencia | Códigos normalizados y fechas en ISO | Reparar |
| `EXPENSES_REQUIRED_FIELDS` | Completitud | Ningún campo vacío | Cuarentena |
| `EXPENSES_VALID_DATE` | Validez | Fecha calendario válida | Cuarentena |
| `EXPENSES_POSITIVE_AMOUNT` | Validez | Importe > 0 | Cuarentena |
| `EXPENSES_KNOWN_BUSINESS_UNIT` | Integridad | La unidad existe | Cuarentena |
| `EXPENSES_KNOWN_COST_CENTER` | Integridad | El centro de costo existe | Cuarentena |
| `EXPENSES_OPERATING_ACCOUNT` | Integridad | La cuenta existe y es de gasto operativo | Cuarentena |
| `EXPENSES_EXACT_DUPLICATES` | Unicidad | Sin asientos duplicados exactos | Deduplicar |
| `EXPENSES_GRAIN_UNIQUE` | Unicidad | `entry_id` es único | **Detener** |
| `BUDGET_REQUIRED_FIELDS` | Completitud | Ningún campo vacío | Cuarentena |
| `BUDGET_VALID_PERIOD` | Validez | Año entero y mes entre 1 y 12 | Cuarentena |
| `BUDGET_VALID_AMOUNT` | Validez | Importe numérico ≥ 0 | Cuarentena |
| `BUDGET_KNOWN_BUSINESS_UNIT` | Integridad | La unidad existe | Cuarentena |
| `BUDGET_KNOWN_ACCOUNT` | Integridad | La cuenta existe | Cuarentena |
| `BUDGET_EXACT_DUPLICATES` | Unicidad | Sin líneas duplicadas exactas | Deduplicar |
| `BUDGET_GRAIN_UNIQUE` | Unicidad | Mes × unidad × cuenta es único | **Detener** |
| `BUDGET_GRID_COMPLETE` | Completitud | Existe una línea para cada mes × unidad × cuenta | **Detener** |
| `*_REJECT_RATE` | Validez | Rechazos ≤ 1 % del extracto | **Detener** |
| `MASTER_*_KEY_UNIQUE` | Unicidad | Clave natural única y no vacía en cada maestro | **Detener** |
| `MASTER_*_REQUIRED` | Completitud | Todos los atributos poblados | **Detener** |
| `MASTER_CATEGORY_NAME_DEPENDENCY` | Consistencia | Un código de categoría, un solo nombre | **Detener** |
| `MASTER_ACCOUNT_TYPE_DOMAIN` | Validez | `account_type` en el dominio permitido | **Detener** |

`EXPENSES_OPERATING_ACCOUNT` es además una defensa contra la doble contabilización: impide
que un costo de ventas o un ingreso entren por el libro de gastos.

### 2.2 Almacén (`stage = WAREHOUSE`)

Se ejecutan contra la base de datos después de cargar y antes de confirmar la transacción.

| Código | Dimensión | Regla |
|--------|-----------|-------|
| `WH_*_ROW_COUNT` | Completitud | Las filas en cada tabla de hechos igualan las enviadas |
| `WH_RECONCILE_UNITS` | Conciliación | Σ unidades = total de control |
| `WH_RECONCILE_GROSS_SALES` | Conciliación | Σ venta bruta = total de control |
| `WH_RECONCILE_DISCOUNTS` | Conciliación | Σ descuentos = total de control |
| `WH_RECONCILE_NET_SALES` | Conciliación | Σ venta neta = total de control |
| `WH_RECONCILE_COGS` | Conciliación | Σ costo de ventas = total de control |
| `WH_RECONCILE_EXPENSES` | Conciliación | Σ gastos = total de control |
| `WH_RECONCILE_BUDGET` | Conciliación | Σ presupuesto = total de control |
| `WH_EXPENSES_ACCOUNT_TYPE` | Consistencia | El hecho de gastos solo usa cuentas operativas |
| `WH_DATE_DIMENSION_CONTINUOUS` | Completitud | `dim_date` no tiene huecos |
| `WH_SALES_MONTHS_COMPLETE` | Completitud | Toda unidad tiene ventas en todos los meses |
| `WH_BUDGET_ACTUAL_ALIGNMENT` | Consistencia | Cada celda tiene presupuesto y ejecución (`WARNING`) |

Las conciliaciones comparan con tolerancia **cero**: los importes son `NUMERIC(14,2)` y los
totales de control están en centavos exactos.

Los **totales de control** provienen de `MANIFEST.json`, que cumple el papel del reporte de
control que emitiría el sistema de origen. En un entorno real ese reporte lo produce un
sistema distinto del que entrega los extractos; aquí ambos salen del mismo generador, lo que
limita la independencia de la conciliación (ver [LIMITATIONS.md](LIMITATIONS.md)).

## 3. Restricciones de la base de datos

Aunque el pipeline valida antes de cargar, la base de datos impone por su cuenta las reglas
estructurales. Si otro proceso intentara escribir datos inválidos, PostgreSQL los
rechazaría.

| Regla | Mecanismo |
|-------|-----------|
| Grano único de cada hecho | Clave primaria |
| Integridad referencial | Claves foráneas |
| Unidades > 0, importes ≥ 0, gasto > 0 | `CHECK` |
| Venta neta = bruta − descuento | `CHECK` |
| Presupuesto anclado al primer día del mes | `CHECK` |
| Dominios de `account_type` y `cost_behavior` | `CHECK` |
| `date_key` coherente con `full_date` | `CHECK` |

Cada restricción tiene una prueba que intenta violarla
(`tests/integration/test_pipeline.py`).

## 4. Consultas SQL de validación

[`database/sql/validation_queries.sql`](../database/sql/validation_queries.sql) contiene 16
consultas escritas aparte del código del ETL. Cada una devuelve las filas que **violan** una
regla, así que un almacén sano devuelve cero filas en todas.

```bash
scripts/run_validation_queries.sh
```

| Consulta | Qué verifica |
|----------|--------------|
| `fact_sales_grain_is_unique`, `fact_budget_grain_is_unique` | Unicidad del grano |
| `fact_sales_net_equals_gross_minus_discount` | Identidad de la venta neta |
| `*_has_no_orphan_keys` (3) | Ninguna clave foránea huérfana |
| `fact_budget_month_key_is_first_day_of_month` | Anclaje mensual del presupuesto |
| `operating_expenses_use_only_operating_accounts` | Sin doble contabilización por cuenta |
| `budget_grid_is_complete` | Presupuesto completo para cada mes × unidad × cuenta |
| `dim_date_has_no_gaps`, `dim_date_covers_whole_months` | Calendario continuo y meses completos |
| `category_code_maps_to_one_name` | Jerarquía de producto coherente |
| `every_business_unit_sells_every_month` | Sin meses vacíos por unidad |
| `actuals_view_reconciles_with_facts` | La vista de ejecución conserva los totales de los hechos |
| `comparison_view_grain_is_unique` | La vista de comparación no multiplica filas |
| `no_product_sells_below_cost_overall` | Ningún producto con margen acumulado negativo |

Resultado sobre los datos de referencia: **16 de 16 consultas sin violaciones**.

## 5. Dónde se consulta

- **Aplicación:** vista *Data Quality*, con la última ejecución, el balance de filas por
  extracto y el resultado de cada regla.
- **API:** `GET /api/v1/data-quality`.
- **Base de datos:** tablas `etl_run`, `etl_table_load` y `etl_data_quality_check`.
- **Archivos:** `data/processed/rejected/` conserva cada fila apartada y su motivo.
