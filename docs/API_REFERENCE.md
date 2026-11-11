# Referencia de la API

API REST de solo lectura construida con FastAPI. La especificación OpenAPI generada desde
el código es la referencia exacta de parámetros y esquemas:

- Documentación interactiva: `http://127.0.0.1:8000/api/v1/docs`
- Esquema OpenAPI: `http://127.0.0.1:8000/api/v1/openapi.json`

Este documento resume el diseño y las convenciones.

## 1. Convenciones

| Aspecto | Convención |
|---------|------------|
| Prefijo | `/api/v1` |
| Métodos | Solo `GET`; la API no modifica datos |
| Meses | Cadenas `AAAA-MM` |
| Importes | USD, redondeados a 2 decimales |
| Razones | Fracciones (0,25 = 25 %), redondeadas a 6 decimales |
| `null` | El valor no está definido para la selección (margen sin ingresos, comparación sin datos) |
| Autenticación | Ninguna ([LIMITATIONS.md](LIMITATIONS.md)) |

## 2. Filtros globales

Todos los endpoints analíticos aceptan los mismos parámetros:

| Parámetro | Tipo | Por defecto | Descripción |
|-----------|------|-------------|-------------|
| `start` | `AAAA-MM` | 12 meses hasta `end` | Primer mes del periodo |
| `end` | `AAAA-MM` | Último mes con datos | Último mes del periodo |
| `business_unit` | código, repetible | Todas | `RET`, `ECM`, `WHS`, `COR`. No distingue mayúsculas |
| `compare` | `previous_year` \| `previous_period` | `previous_year` | Base de comparación |

Cada respuesta incluye un campo `filters` con el contexto **realmente aplicado**: periodo,
unidades, periodo de comparación y si este está disponible.

```json
"filters": {
  "start": "2025-01", "end": "2025-12", "months": 12,
  "period_label": "Jan 2025 - Dec 2025",
  "business_units": [],
  "compare": "previous_year",
  "comparison_available": true,
  "comparison_start": "2024-01", "comparison_end": "2024-12",
  "comparison_label": "Jan 2024 - Dec 2024"
}
```

Cuando el periodo de comparación queda fuera de los datos disponibles,
`comparison_available` es `false` y los campos de comparación llegan como `null`. No se
compara contra un periodo parcial.

## 3. Endpoints

### Servicio y catálogos

| Endpoint | Descripción |
|----------|-------------|
| `GET /health` | Estado del servicio y de la base de datos, fecha de la última carga y periodo disponible. Devuelve 503 si la base de datos no responde |
| `GET /dimensions` | Unidades de negocio, categorías, productos, centros de costo, cuentas y periodo disponible |
| `GET /kpi-catalog` | Definición formal de cada KPI |
| `GET /data-quality` | Última ejecución del pipeline, balance de filas, reglas de calidad e historial |

### Indicadores y series

| Endpoint | Parámetros propios | Descripción |
|----------|--------------------|-------------|
| `GET /kpis/summary` | — | Siete KPI con valor, comparación, presupuesto, favorabilidad y serie mensual |
| `GET /timeseries` | — | Estado de resultados mensual con presupuesto, crecimiento intermensual e interanual y media móvil de 3 meses |
| `GET /timeseries/business-units` | — | Ingresos, utilidades y márgenes mensuales por unidad |

### Presupuesto frente a ejecución

| Endpoint | Parámetros propios | Descripción |
|----------|--------------------|-------------|
| `GET /budget/statement` | — | Estado de resultados por cuenta con subtotales, variación e impacto en utilidad |
| `GET /budget/variance` | `group_by` = `month` \| `business_unit` | Variación de ingresos, costos, gastos y utilidad operativa por grupo |
| `GET /budget/matrix` | — | Variación de cada celda unidad × cuenta |

### Rentabilidad y gastos

| Endpoint | Parámetros propios | Descripción |
|----------|--------------------|-------------|
| `GET /profitability` | `group_by` = `business_unit` \| `category` \| `product`; `category` | Ventas, descuentos, margen bruto y participación por segmento |
| `GET /expenses/breakdown` | `group_by` = `account` \| `account_group` \| `cost_center` \| `cost_behavior` | Gasto operativo por grupo, con presupuesto y comparación |
| `GET /expenses/matrix` | — | Gasto por centro de costo × grupo de cuentas |

Dos restricciones que provienen del modelo de datos:

- `/profitability` incluye utilidad operativa solo con `group_by=business_unit` y sin filtro
  de categoría: los gastos operativos no se registran por producto.
- `/expenses/breakdown` con `group_by=cost_center` devuelve `null` en los campos de
  presupuesto: el presupuesto no se planea por centro de costo.

### Análisis

| Endpoint | Parámetros propios | Descripción |
|----------|--------------------|-------------|
| `GET /analysis/operating-income-bridge` | `basis` = `comparison` \| `budget` | Puente de utilidad operativa; los pasos suman exactamente la variación |
| `GET /analysis/price-volume-mix` | `group_by` = `category` \| `business_unit` | Efectos precio, volumen y mezcla sobre el cambio de ingresos |
| `GET /analysis/margin-drivers` | `group_by` = `category` \| `business_unit` | Efectos mezcla y tasa sobre el cambio del margen bruto |
| `GET /analysis/anomalies` | `include_immaterial` (booleano) | Meses con variación presupuestal estadísticamente inusual |
| `GET /insights` | — | Hallazgos calculados para los filtros vigentes, con su evidencia |

Los análisis que necesitan un periodo de comparación devuelven `available: false` y listas
vacías cuando ese periodo no tiene datos.

### Tabla analítica y exportaciones

| Endpoint | Parámetros propios | Descripción |
|----------|--------------------|-------------|
| `GET /records/monthly` | `page` (≥ 1), `page_size` (1–200), `sort_by`, `sort_dir` | Estado de resultados mensual por unidad, paginado y ordenable |
| `GET /exports/{dataset}` | — | Descarga CSV con los filtros vigentes |

Conjuntos exportables: `monthly-pnl`, `budget-by-account`, `sales-by-product`,
`expenses-by-cost-center` y `anomalies`. El nombre del archivo incluye el periodo y las
unidades, por ejemplo `monthly-pnl_2025-01_2025-12_all-units.csv`. Los CSV se generan con
las mismas funciones que las respuestas JSON, de modo que las cifras exportadas coinciden
con las de pantalla.

La paginación se devuelve en un objeto `pagination`:

```json
"pagination": { "page": 1, "page_size": 12, "total_items": 48, "total_pages": 4 }
```

## 4. Errores

| Código | Situación | Cuerpo |
|--------|-----------|--------|
| 422 | Parámetro con formato inválido (por ejemplo `start=2025-13`) | Formato de validación de FastAPI, con el parámetro y el motivo |
| 422 | Filtro no aplicable a los datos: periodo fuera del rango disponible, inicio posterior al fin, unidad o categoría inexistente | `{"detail": "mensaje con los valores válidos"}` |
| 503 | La base de datos no responde | `{"detail": "The database is unavailable."}` |
| 503 | El almacén está vacío | `{"detail": "The warehouse is empty. Run the ETL pipeline first."}` |
| 405 | Método distinto de `GET` | — |

Los mensajes de error de base de datos nunca incluyen detalles de conexión.

## 5. Ejemplos

```bash
# KPI de 2025 de E-commerce frente al año anterior
curl "http://127.0.0.1:8000/api/v1/kpis/summary?start=2025-01&end=2025-12&business_unit=ECM"

# Variación presupuestal por unidad de negocio en el segundo trimestre de 2024
curl "http://127.0.0.1:8000/api/v1/budget/variance?start=2024-04&end=2024-06&group_by=business_unit"

# Atípicos de todo el historial, incluidos los no materiales
curl "http://127.0.0.1:8000/api/v1/analysis/anomalies?start=2023-01&end=2025-12&include_immaterial=true"

# Exportar el estado de resultados mensual de dos unidades
curl -OJ "http://127.0.0.1:8000/api/v1/exports/monthly-pnl?start=2025-01&end=2025-12&business_unit=RET&business_unit=ECM"
```

Fragmento de `GET /kpis/summary` para 2025, todas las unidades:

```json
{
  "id": "net_revenue",
  "label": "Net revenue",
  "unit": "currency",
  "higher_is_better": true,
  "value": 59053741.75,
  "comparison_value": 52097564.14,
  "change": 6956177.61,
  "change_pct": 0.133522,
  "comparison_status": "favorable",
  "budget_value": 58697700.0,
  "budget_variance": 356041.75,
  "budget_variance_pct": 0.006066,
  "budget_status": "favorable",
  "sparkline": ["12 valores mensuales"]
}
```

## 6. Diseño interno

```
Router (api/routers)          parámetros, validación y documentación OpenAPI
   │
Contexto (services/context)   filtros validados contra los datos; tablas cargadas una vez por solicitud
   │
Servicios (services/*)        arman las respuestas tipadas
   ├── Analítica (analytics/*)       funciones puras: fórmulas, descomposiciones, atípicos
   └── Repositorio (repositories/*)  SQL de solo lectura, agregado al mes
```

- **Agregación en SQL, análisis en pandas.** El repositorio devuelve tablas de pocos miles de
  filas ya agregadas al mes; ninguna consulta trae filas diarias a la aplicación.
- **Sin caché.** Las consultas base tardan entre 12 y 22 ms sobre el volumen del proyecto
  (medido con `\timing` en psql); una caché añadiría estado e invalidación sin beneficio
  perceptible.
- **Un contexto por solicitud.** Todos los cálculos de una respuesta parten de la misma
  lectura, así que sus cifras son coherentes entre sí.
