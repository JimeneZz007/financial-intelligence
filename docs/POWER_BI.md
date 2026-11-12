# Informe Power BI

> **Estado: el archivo `.pbix` está PENDIENTE.** Power BI Desktop solo existe para Windows
> y el entorno de desarrollo es macOS, así que el informe no se ha construido. Este
> repositorio no contiene ningún `.pbix` ni capturas de Power BI.
>
> Lo que sí se entrega son los insumos para construirlo y comprobarlo: los datos del modelo
> estrella, las consultas Power Query, las medidas DAX, el tema y los valores esperados.
> Las consultas M, las medidas DAX y el tema **no se han ejecutado en Power BI**; son una
> especificación hasta que pasen la verificación de la sección 6.

## 1. Qué hay en `powerbi/`

| Ruta | Contenido | Estado |
|------|-----------|--------|
| `data/*.csv` | Modelo estrella exportado por el pipeline (no versionado; se genera con `make powerbi-data`) | Verificado: sale del mismo ETL que alimenta PostgreSQL |
| `queries/star_schema.pq` | Una consulta Power Query (M) por tabla, con tipos explícitos | Sin ejecutar en Power BI |
| `measures/measures.dax` | 50 medidas DAX en siete carpetas | Sin ejecutar en Power BI |
| `theme/financial-intelligence.json` | Tema con la paleta del proyecto | JSON válido; sin importar en Power BI |
| `validation/expected_values.csv` | 116 valores que las medidas deben mostrar | Verificado contra la base de datos y la API |

```bash
make pipeline        # genera los datos, migra y carga el almacén
make powerbi-data    # copia el modelo estrella a powerbi/data/ y recalcula los valores esperados
```

## 2. Modelo

El informe usa el **mismo modelo dimensional** que la aplicación web
([DATA_MODEL.md](DATA_MODEL.md)): tres hechos y cinco dimensiones conformadas.

### Relaciones

Todas son de uno a varios, con dirección de filtro única (de la dimensión al hecho).

| Desde (lado uno) | Hacia (lado varios) |
|------------------|---------------------|
| `dim_date[date_key]` | `fact_sales[date_key]` |
| `dim_date[date_key]` | `fact_operating_expenses[date_key]` |
| `dim_date[date_key]` | `fact_budget[month_date_key]` |
| `dim_business_unit[business_unit_key]` | `fact_sales`, `fact_operating_expenses`, `fact_budget` |
| `dim_product[product_key]` | `fact_sales[product_key]` |
| `dim_cost_center[cost_center_key]` | `fact_operating_expenses[cost_center_key]` |
| `dim_account[account_key]` | `fact_operating_expenses[account_key]`, `fact_budget[account_key]` |

No hay relaciones entre hechos ni relaciones bidireccionales: los hechos se combinan solo a
través de las dimensiones que comparten, lo que impide la doble contabilización.

### Configuración del modelo

- Marcar `dim_date` como **tabla de fechas** con `full_date`.
- Ordenar por columna: `month_name` y `month_short` por `month`; `year_month` por
  `month_start_key`; `day_name` por `day_of_week`; `account_name` por `statement_order`.
- Ocultar en la vista de informe las claves sustitutas y las columnas numéricas de los
  hechos, para que solo se usen las medidas.
- Desactivar la fecha y hora automáticas (Opciones > Carga de datos).

### Dos consecuencias del grano

- **El presupuesto es mensual.** `fact_budget` se relaciona con el primer día de cada mes.
  Un objeto visual con presupuesto debe usar mes, trimestre o año; a nivel de día el
  presupuesto aparecería completo en el día 1.
- **Los gastos no tienen producto.** `[Operating Income]` y `[Expense Ratio %]` devuelven
  `BLANK` cuando hay un producto o categoría en el contexto, en lugar de restar a un margen
  bruto parcial el gasto total.

## 3. Medidas DAX

Definidas en [`measures/measures.dax`](../powerbi/measures/measures.dax). Reproducen el
[catálogo de KPI](KPI_CATALOG.md).

| Carpeta | Medidas |
|---------|---------|
| 1 Sales | Net Revenue, Gross Sales, Discounts, Discount Rate %, Units Sold, Net Revenue per Unit, Revenue Share of Units %, Revenue Share of Products % |
| 2 Profitability | Direct Costs, Gross Profit, Gross Margin %, Operating Expenses, Operating Income, Operating Margin %, Expense Ratio % |
| 3 Budget | Budget Revenue, Budget Direct Costs, Budget Operating Expenses, Budget Gross Profit, Budget Operating Income, Budget Operating Margin % |
| 4 Variance | Variación absoluta y porcentual de ingresos, costos directos, gastos y utilidad operativa; Revenue Attainment %; tres medidas de estado (Favorable / Unfavorable / On target) |
| 5 Statement by account | Actual Amount, Budget Amount, Account Variance, Account Variance %, Profit Impact |
| 6 Time intelligence | Net Revenue PY, YoY %, PM, MoM %, YTD, 3M Average; Operating Income PY y YoY %; Gross Margin PY % y Gross Margin Change pp |
| 7 Labels | Selected Period, Data Notice |

Decisiones de diseño de las medidas:

- **Razón de sumas.** Los márgenes usan `DIVIDE` sobre medidas agregadas; `DIVIDE` devuelve
  `BLANK` si el denominador es cero.
- **Presupuesto por tipo de cuenta con `KEEPFILTERS`**, para respetar una cuenta
  seleccionada en un segmentador en lugar de sobrescribirla.
- **`[Actual Amount]` une las ventas al plan de cuentas.** Las ventas no se relacionan con
  `dim_account`; la medida asigna los ingresos netos a la cuenta de tipo `REVENUE` y el
  costo de ventas a la de tipo `DIRECT_COST`, igual que la vista
  `vw_actual_by_account_month`.
- **`[Profit Impact]` es la única medida por cuenta cuyo total tiene sentido.** Sumar
  ingresos con gastos no significa nada; el impacto en utilidad sí es aditivo y su total es
  la variación de la utilidad operativa.
- **Los cambios de margen se expresan en puntos porcentuales**, como diferencia de razones.

## 4. Construcción del informe

1. Ejecutar `make pipeline` y `make powerbi-data`. Copiar la carpeta `powerbi/` al equipo
   Windows si es otro.
2. En Power BI Desktop: Transformar datos > Administrar parámetros > crear `DataFolder`
   (texto) con la ruta completa de `powerbi\data\`, terminada en barra invertida.
3. Crear la función `fnReadCsv` y una consulta por tabla con el contenido de
   `queries/star_schema.pq`.
4. Crear las relaciones de la sección 2 y aplicar la configuración del modelo.
5. Crear la tabla `Measures` y añadir las medidas de `measures/measures.dax`.
6. Importar el tema: Ver > Temas > Examinar temas > `theme/financial-intelligence.json`.
7. Construir las páginas de la sección 5.
8. Verificar con la sección 6 antes de dar por bueno el informe.

**Fuente alternativa.** Las consultas pueden leer de PostgreSQL en lugar de los CSV (el
fragmento está al final del archivo `.pq`). Requiere que la base de datos sea accesible
desde el equipo Windows y el proveedor Npgsql.

## 5. Especificación de las páginas

Lienzo de 1280 × 720. En todas las páginas: título, segmentadores de **año**
(`dim_date[year]`), **mes** (`dim_date[month_short]`) y **unidad de negocio**
(`dim_business_unit[business_unit_name]`) sincronizados entre páginas, y una tarjeta con
`[Data Notice]`.

### Página 1 · Executive Overview

| Objeto visual | Campos |
|---------------|--------|
| 4 tarjetas | `[Net Revenue]`, `[Direct Costs]`, `[Operating Income]`, `[Operating Margin %]`; como referencia, `[Net Revenue YoY %]` y `[Revenue Variance %]` |
| Columnas y línea (un solo eje) | Eje: `year_month`; columnas: `[Net Revenue]`; línea: `[Budget Revenue]` |
| Barras agrupadas | Eje: líneas del estado de resultados; valores: ejecución y presupuesto |
| Barras horizontales | Eje: `category_name`; valor: `[Net Revenue]` |
| Matriz | Filas: `business_unit_name`; valores: `[Net Revenue]`, `[Gross Margin %]`, `[Operating Income]`, `[Operating Margin %]`, `[Revenue Variance %]` |

### Página 2 · Revenue

| Objeto visual | Campos |
|---------------|--------|
| Tarjetas | `[Net Revenue]`, `[Gross Sales]`, `[Discount Rate %]`, `[Units Sold]` |
| Columnas apiladas | Eje: `year_month`; leyenda: `business_unit_name`; valor: `[Net Revenue]` |
| Líneas | Eje: `year_month`; valores: `[Net Revenue MoM %]`, `[Net Revenue YoY %]` |
| Matriz con jerarquía | Filas: `category_name` > `product_name`; valores: `[Units Sold]`, `[Net Revenue]`, `[Revenue Share of Products %]`, `[Discount Rate %]`, `[Gross Margin %]` |

### Página 3 · Costs & Expenses

| Objeto visual | Campos |
|---------------|--------|
| Tarjetas | `[Direct Costs]`, `[Operating Expenses]`, `[Expense Ratio %]`, `[Operating Expenses Variance %]` |
| Barras horizontales | Eje: `account_group`; valores: `[Operating Expenses]`, `[Budget Operating Expenses]` |
| Matriz (mapa de calor con formato condicional) | Filas: `account_group`; columnas: `cost_center_name`; valor: `[Operating Expenses]` |
| Líneas | Eje: `year_month`; valor: `[Expense Ratio %]` |

### Página 4 · Profitability

| Objeto visual | Campos |
|---------------|--------|
| Tarjetas | `[Gross Margin %]`, `[Operating Margin %]`, `[Gross Margin Change pp]`, `[Operating Income YoY %]` |
| Barras agrupadas | Eje: `business_unit_name`; valores: `[Gross Margin %]`, `[Operating Margin %]` |
| Múltiplos pequeños de líneas | Eje: `year_month`; valor: `[Operating Margin %]`; múltiplos: `business_unit_name` |
| Barras horizontales | Eje: `category_name`; valor: `[Gross Margin %]` |

### Página 5 · Budget vs Actual

| Objeto visual | Campos |
|---------------|--------|
| Tarjetas | `[Revenue Attainment %]`, `[Operating Income Variance]`, `[Operating Expenses Variance %]` |
| Columnas con formato condicional por estado | Eje: `year_month`; valor: `[Operating Income Variance]` |
| Matriz del estado de resultados | Filas: `account_name`; valores: `[Actual Amount]`, `[Budget Amount]`, `[Account Variance]`, `[Account Variance %]`, `[Profit Impact]` |
| Cascada | Categoría: `account_group`; valor: `[Profit Impact]` |

Reglas de diseño, las mismas que en la aplicación web ([UI_DESIGN.md](UI_DESIGN.md)): un
solo eje por gráfico, sin gráficos circulares, y el par verde azulado y coral del tema
(`good` / `bad`) para favorable y desfavorable.

**Lo que el informe no replica.** El puente de precio, volumen y mezcla, la descomposición
de mezcla y tasa y la detección de atípicos están implementados en Python en la aplicación
web. No se han trasladado a DAX.

## 6. Verificación

[`validation/expected_values.csv`](../powerbi/validation/expected_values.csv) contiene 116
valores calculados con SQL directo sobre las tablas de hechos, sin usar DAX ni el código de
la API. Cada fila indica los segmentadores, el contexto del objeto visual, la medida y el
valor que debe aparecer.

| Segmentadores | Contexto | Medida | Valor esperado |
|---------------|----------|--------|---------------:|
| Ninguno | Tarjeta | Net Revenue | 160 488 192,49 |
| Ninguno | Tarjeta | Operating Income | 10 982 268,71 |
| Year = 2025 | Tarjeta | Net Revenue | 59 053 741,75 |
| Year = 2025 | Tarjeta | Operating Income Variance | −898 130,32 |
| Year = 2025 | Fila: Electronics | Gross Margin % | 14,2345 % |
| year_month = 2025-03 | Tarjeta | Net Revenue YoY % | 12,1095 % |
| year_month = 2025-03 | Tarjeta | Net Revenue YTD | 12 625 617,49 |
| year_month = 2023-03 | Tarjeta | Net Revenue YoY % | (en blanco) |
| Year = 2025 | Total de la matriz por cuenta | Profit Impact | −898 130,32 |

Procedimiento: reproducir cada selección en el informe y comparar. Si las 116 coinciden, el
modelo, las relaciones y las medidas son correctos; una diferencia localiza el error en la
medida o en la relación implicada.

Tres pruebas automatizadas protegen este archivo
(`tests/integration/test_powerbi_assets.py`): que coincide con un cálculo nuevo sobre la
base de datos, que concuerda con la API, y que cada medida con valor esperado está definida
en el archivo DAX.

## 7. Pendiente

| Elemento | Estado |
|----------|--------|
| Archivo `.pbix` | **PENDIENTE**: requiere Power BI Desktop (Windows) |
| Ejecución de las consultas M | Sin verificar |
| Ejecución de las medidas DAX y comparación con los valores esperados | Sin verificar |
| Importación del tema | Sin verificar |
| Capturas del informe | No existen |
