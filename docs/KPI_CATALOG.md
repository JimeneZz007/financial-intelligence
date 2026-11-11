# Catálogo de KPI

Definiciones formales de los indicadores. La referencia ejecutable está en
[`backend/app/core/kpi_catalog.py`](../backend/app/core/kpi_catalog.py), se sirve en
`GET /api/v1/kpi-catalog` y se muestra en la vista *Methodology*. Una prueba automatizada
comprueba que este documento cubre todos los KPI del catálogo en código.

## Convenciones

- **Moneda:** USD. **Razones:** fracciones (0,25 = 25 %).
- **Razón de sumas.** Todo porcentaje se calcula como cociente de totales del segmento
  seleccionado. Nunca se promedian porcentajes de subsegmentos.
- **Nulos.** Un indicador no definido se reporta como `null`, nunca como 0 ni infinito.
- **Favorabilidad.** Una variación es *favorable* si mejora la utilidad: positiva en
  ingresos y utilidades, negativa en costos y gastos. Si es menor al 0,5 % de la referencia
  se reporta *en línea* (`on_target`).
- **Filtros.** Los indicadores que combinan ventas y gastos solo admiten periodo y unidad
  de negocio, las dimensiones compartidas por todos los hechos
  ([D-006](DECISIONS.md)).

## Estructura del estado de resultados

```
  Ingresos netos                 Σ fact_sales.net_sales_amount
− Costos directos                Σ fact_sales.cogs_amount
= Utilidad bruta
− Gastos operativos              Σ fact_operating_expenses.amount
= Utilidad operativa
```

## Indicadores

### `net_revenue` — Ingresos netos

| | |
|---|---|
| **Fórmula** | `SUM(fact_sales.net_sales_amount)`, donde neta = venta bruta − descuentos |
| **Unidad** | USD |
| **Grano** | Aditivo en día × unidad × producto; se reporta por mes |
| **Filtros** | Periodo, unidad de negocio, categoría, producto |
| **Nulos** | La columna es `NOT NULL`. Un segmento sin ventas reporta 0 |
| **Interpretación** | Ventas facturadas después de descuentos. Mayor es mejor |
| **Limitaciones** | No se modelan devoluciones, impuestos ni bonificaciones |

### `direct_costs` — Costos directos

| | |
|---|---|
| **Fórmula** | `SUM(fact_sales.cogs_amount)` |
| **Unidad** | USD |
| **Grano** | Aditivo en día × unidad × producto; se reporta por mes |
| **Filtros** | Periodo, unidad de negocio, categoría, producto |
| **Nulos** | La columna es `NOT NULL`. Un segmento sin ventas reporta 0 |
| **Interpretación** | Costo de la mercancía vendida. Menor es mejor para un ingreso dado |
| **Limitaciones** | Costo unitario al momento de la venta; sin efectos de valoración de inventario |

### `gross_profit` — Utilidad bruta

| | |
|---|---|
| **Fórmula** | `net_revenue − direct_costs` |
| **Unidad** | USD |
| **Grano** | Aditivo; derivado del hecho de ventas |
| **Filtros** | Periodo, unidad de negocio, categoría, producto |
| **Nulos** | Siempre definido |
| **Interpretación** | Lo que queda del ingreso después del costo de la mercancía. Mayor es mejor |
| **Limitaciones** | Excluye todos los gastos operativos |

### `gross_margin` — Margen bruto

| | |
|---|---|
| **Fórmula** | `gross_profit / net_revenue` |
| **Unidad** | % (razón) |
| **Grano** | No aditivo: razón de sumas del segmento seleccionado |
| **Filtros** | Periodo, unidad de negocio, categoría, producto |
| **Nulos** | `null` cuando los ingresos netos son 0 |
| **Interpretación** | Parte de cada dólar de ingreso que se conserva tras los costos directos |
| **Limitaciones** | Un cambio de margen mezcla efectos de precio, costo y mezcla; el análisis de mezcla y tasa los separa |

### `operating_expenses` — Gastos operativos

| | |
|---|---|
| **Fórmula** | `SUM(fact_operating_expenses.amount)` |
| **Unidad** | USD |
| **Grano** | Aditivo en asiento; se reporta por mes |
| **Filtros** | Periodo, unidad de negocio, centro de costo, cuenta |
| **Nulos** | La columna es `NOT NULL` y > 0. Un segmento sin asientos reporta 0 |
| **Interpretación** | Costo de operar el negocio sin contar la mercancía. Menor es mejor |
| **Limitaciones** | No se puede dividir por producto o categoría: el libro no tiene esa dimensión |

### `operating_income` — Utilidad operativa

| | |
|---|---|
| **Fórmula** | `gross_profit − operating_expenses` |
| **Unidad** | USD |
| **Grano** | Derivado por *drill-across*: ambos hechos se agregan primero a mes × unidad |
| **Filtros** | Periodo, unidad de negocio |
| **Nulos** | Siempre definido |
| **Interpretación** | Resultado de la operación antes de intereses e impuestos. Mayor es mejor |
| **Limitaciones** | Solo por periodo y unidad; incluye depreciación (comparable a un EBIT) |

### `operating_margin` — Margen operativo

| | |
|---|---|
| **Fórmula** | `operating_income / net_revenue` |
| **Unidad** | % (razón) |
| **Grano** | No aditivo: razón de sumas del segmento seleccionado |
| **Filtros** | Periodo, unidad de negocio |
| **Nulos** | `null` cuando los ingresos netos son 0 |
| **Interpretación** | Utilidad operativa por dólar de ingreso. Mayor es mejor |
| **Limitaciones** | Solo por periodo y unidad de negocio |

### `budget` — Presupuesto

| | |
|---|---|
| **Fórmula** | `SUM(fact_budget.budget_amount)` de las cuentas de la medida |
| **Unidad** | USD |
| **Grano** | Aditivo en mes × unidad × cuenta, dentro de un mismo tipo de cuenta |
| **Filtros** | Periodo (meses completos), unidad de negocio, cuenta |
| **Nulos** | La malla presupuestal es completa por una regla de calidad bloqueante |
| **Interpretación** | El plan aprobado para el periodo |
| **Limitaciones** | Una sola versión aprobada; sin pronósticos. No se planea por producto ni por centro de costo |

### `actual` — Ejecución

| | |
|---|---|
| **Fórmula** | `vw_actual_by_account_month`: venta neta → cuenta 4000; costo de ventas → cuenta 5000; gasto operativo → su cuenta 6xxx |
| **Unidad** | USD |
| **Grano** | Mes × unidad × cuenta (el grano del presupuesto) |
| **Filtros** | Periodo (meses completos), unidad de negocio, cuenta |
| **Nulos** | Una celda sin transacciones se trata como 0 |
| **Interpretación** | Lo realmente vendido o gastado, al grano del presupuesto |
| **Limitaciones** | La correspondencia de las ventas con las cuentas 4000 y 5000 es fija en la definición de la vista |

### `budget_variance` — Variación absoluta

| | |
|---|---|
| **Fórmula** | `actual − budget` |
| **Unidad** | USD |
| **Grano** | Aditivo dentro de un mismo tipo de cuenta |
| **Filtros** | Periodo, unidad de negocio, cuenta |
| **Nulos** | Siempre definido |
| **Interpretación** | Favorable si mejora la utilidad: positiva en ingresos, negativa en costos. *En línea* si es menor al 0,5 % del presupuesto |
| **Limitaciones** | No separa las variaciones de costo debidas al volumen de las debidas a la tarifa |

El **impacto en utilidad** (`profit_impact`) expresa cualquier variación con un único signo:
positivo si mejora la utilidad operativa. La suma de los impactos de todas las cuentas es
exactamente la variación de la utilidad operativa.

### `budget_variance_pct` — Variación porcentual

| | |
|---|---|
| **Fórmula** | `(actual − budget) / |budget|` |
| **Unidad** | % (razón) |
| **Grano** | No aditivo: razón de sumas del segmento seleccionado |
| **Filtros** | Periodo, unidad de negocio, cuenta |
| **Nulos** | `null` cuando el presupuesto es 0 |
| **Interpretación** | Tamaño de la variación respecto al plan |
| **Limitaciones** | Inestable con presupuestos muy pequeños; debe leerse junto con la variación absoluta |

### `mom_growth` — Crecimiento intermensual

| | |
|---|---|
| **Fórmula** | `(valor[m] − valor[m−1]) / |valor[m−1]|` |
| **Unidad** | % (razón) |
| **Grano** | Mes |
| **Filtros** | Periodo, unidad de negocio |
| **Nulos** | `null` en el primer mes del historial o si el valor anterior es 0 |
| **Interpretación** | Impulso de corto plazo |
| **Limitaciones** | No está desestacionalizado: refleja el calendario tanto como el desempeño |

### `yoy_growth` — Crecimiento interanual

| | |
|---|---|
| **Fórmula** | `(valor[m] − valor[m−12]) / |valor[m−12]|` |
| **Unidad** | % (razón) |
| **Grano** | Mes, o cualquier periodo frente a los mismos meses del año anterior |
| **Filtros** | Periodo, unidad de negocio |
| **Nulos** | `null` en los primeros 12 meses del historial o si la base es 0 |
| **Interpretación** | Crecimiento neto de estacionalidad |
| **Limitaciones** | Disponible desde el segundo año de datos (2024) |

Ambos crecimientos se calculan sobre todo el historial y después se recortan al periodo
seleccionado, de modo que el primer mes visible conserva su tasa si existen datos previos.

### `discount_rate` — Tasa de descuento

| | |
|---|---|
| **Fórmula** | `SUM(discount_amount) / SUM(gross_sales_amount)` |
| **Unidad** | % (razón) |
| **Grano** | No aditivo: razón de sumas del segmento seleccionado |
| **Filtros** | Periodo, unidad de negocio, categoría, producto |
| **Nulos** | `null` cuando la venta bruta es 0 |
| **Interpretación** | Parte de la venta a precio realizado cedida en descuentos. Menor es mejor |
| **Limitaciones** | No distingue descuentos promocionales de negociados |

### `revenue_share` — Participación en ingresos

| | |
|---|---|
| **Fórmula** | `net_revenue` del segmento / `net_revenue` de todos los segmentos de la selección |
| **Unidad** | % (razón) |
| **Grano** | Segmento dentro de los filtros vigentes |
| **Filtros** | Periodo, unidad de negocio, categoría, producto |
| **Nulos** | `null` cuando el ingreso total es 0 |
| **Interpretación** | Peso de una unidad, categoría o producto en las ventas |
| **Limitaciones** | Es relativa al total filtrado, no al total de la empresa |

### `expense_ratio` — Gasto sobre ingresos

| | |
|---|---|
| **Fórmula** | `operating_expenses / net_revenue` |
| **Unidad** | % (razón) |
| **Grano** | No aditivo: razón de sumas del segmento seleccionado |
| **Filtros** | Periodo, unidad de negocio |
| **Nulos** | `null` cuando los ingresos netos son 0 |
| **Interpretación** | Costo operativo de generar un dólar de ingreso. Menor es mejor |
| **Limitaciones** | Los costos fijos lo reducen de forma mecánica cuando el ingreso crece |

## Periodos de comparación

| Modo | Periodo de comparación |
|------|------------------------|
| `previous_year` | Los mismos meses un año antes |
| `previous_period` | El periodo de igual duración inmediatamente anterior |

Si el periodo de comparación no está completo en los datos disponibles, la comparación se
reporta como `null`: no se compara contra un periodo parcial.

Los márgenes se comparan en **puntos porcentuales** (diferencia de razones), no en
variación relativa.

## Verificación

Cada indicador se comprueba por tres caminos independientes
([TESTING.md](TESTING.md)): contra un recálculo con pandas sobre los datos del generador,
contra SQL directo sobre las tablas de hechos y por consistencia interna entre endpoints
(por ejemplo, la suma de las unidades de negocio es igual al total de la empresa).
