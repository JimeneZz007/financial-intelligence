# Problema de negocio

> **Aviso.** Grupo Comercial Altamira es una **empresa ficticia**. Todos los datos del
> proyecto son **sintéticos** y se generan con un proceso reproducible descrito en
> [DATA_GENERATION.md](DATA_GENERATION.md). Ninguna cifra representa a una empresa real.

## 1. Contexto

Grupo Comercial Altamira comercializa productos de tecnología, oficina, mobiliario, hogar y
accesorios a través de cuatro unidades de negocio:

| Código | Unidad de negocio | Modelo comercial |
|--------|-------------------|------------------|
| `RET` | Retail Stores | Tiendas físicas, venta al consumidor final |
| `ECM` | E-commerce | Canal digital propio, envíos a domicilio |
| `WHS` | Wholesale Distribution | Venta por volumen a distribuidores |
| `COR` | Corporate Solutions | Contratos de suministro con empresas |

La empresa cierra mensualmente y elabora un presupuesto anual por unidad de negocio y
cuenta. La información vive en extractos separados (ventas, libro de gastos, plan
presupuestal) y el área de planeación financiera (FP&A) la consolida manualmente en hojas
de cálculo.

## 2. Problema

La dirección financiera no dispone de una vista única, consistente y oportuna que responda:

1. ¿Cuánto vendimos, cuánto costó y cuánto ganamos, y cómo se compara con el plan?
2. ¿Dónde se originan las desviaciones y qué magnitud tiene cada una?
3. ¿Qué meses o cuentas se comportan de forma inusual respecto a su propio historial?

La consolidación manual produce tres síntomas concretos:

- **Definiciones inconsistentes.** "Margen" o "gasto" significan cosas distintas según quién
  prepare el informe.
- **Baja trazabilidad.** No se puede reconstruir un indicador hasta la transacción de origen.
- **Análisis reactivo.** Las desviaciones se detectan tarde y se explican de forma
  anecdótica, sin cuantificar la contribución de cada factor.

## 3. Objetivo

Construir una plataforma analítica que transforme los extractos transaccionales en
indicadores financieros con definiciones formales, comparaciones contra presupuesto y
hallazgos calculados, de modo que cada cifra sea reproducible y trazable.

La plataforma **no** es un sistema contable, un ERP ni una herramienta de registro: consume
datos ya registrados y los analiza.

## 4. Usuarios y decisiones que soporta

| Usuario | Necesidad | Decisión que soporta |
|---------|-----------|----------------------|
| Dirección financiera (CFO) | Resultado consolidado y desviación frente al plan | Priorizar acciones correctivas |
| Analista FP&A | Explicar variaciones por cuenta, unidad y periodo | Ajustar pronósticos y supuestos del presupuesto |
| Gerente de unidad de negocio | Rentabilidad de su unidad y de su mezcla de productos | Decisiones de precio, mezcla y gasto |
| Control interno | Evidencia de calidad e integridad de los datos | Confiar (o no) en un cierre |

## 5. Preguntas de negocio

| ID | Pregunta | Dónde se responde |
|----|----------|-------------------|
| Q1 | ¿Qué unidades generan más ingresos? | Overview, Revenue |
| Q2 | ¿Qué categorías presentan mejores márgenes? | Profitability |
| Q3 | ¿Qué gastos explican las mayores desviaciones? | Budget vs Actual, Costs & Expenses |
| Q4 | ¿Qué periodos muestran cambios relevantes? | Trends & Insights |
| Q5 | ¿Qué diferencias existen entre presupuesto y ejecución? | Budget vs Actual |
| Q6 | ¿Qué factores contribuyen a los cambios de rentabilidad? | Profitability (puente de utilidad, precio-volumen-mezcla) |

## 6. Criterios de éxito

- Cada KPI tiene una definición formal única ([KPI_CATALOG.md](KPI_CATALOG.md)) y la API, la
  interfaz y Power BI usan la misma.
- Los totales de la plataforma concilian con los extractos de origen (totales de control).
- Las desviaciones se descomponen en factores cuya suma coincide exactamente con la
  variación total.
- Los comportamientos atípicos se señalan con un criterio estadístico explícito y con una
  evaluación medida contra escenarios conocidos.
- Todo el proceso se reproduce desde cero con comandos documentados.

## 7. Alcance

**Incluido:** ingresos netos, costos directos, gastos operativos, utilidad bruta y
operativa, márgenes, presupuesto frente a ejecución, tendencias, análisis de contribución y
detección de atípicos, con granularidad mensual y filtros por periodo y unidad de negocio.

**Excluido:** partidas por debajo de la utilidad operativa (intereses, impuestos), balance
general y flujo de caja, pronósticos, asignación de gastos operativos a productos,
multimoneda, autenticación de usuarios y registro de transacciones.

Las exclusiones y sus consecuencias se detallan en [LIMITATIONS.md](LIMITATIONS.md).
