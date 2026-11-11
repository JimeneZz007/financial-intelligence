# Diseño metodológico

El proyecto combina **CRISP-DM** como marco del proceso analítico, **Kimball** para el
modelado de datos y un **desarrollo iterativo** por entregas verticales.

## 1. CRISP-DM aplicado

| Fase | Pregunta que resuelve | Entregable en este repositorio |
|------|-----------------------|--------------------------------|
| 1. Comprensión del negocio | ¿Qué decisiones debe soportar la plataforma? | [BUSINESS_PROBLEM.md](BUSINESS_PROBLEM.md) |
| 2. Comprensión de los datos | ¿Qué fuentes existen, con qué grano y calidad? | [DATA_GENERATION.md](DATA_GENERATION.md), [DATA_DICTIONARY.md](DATA_DICTIONARY.md) |
| 3. Preparación de los datos | ¿Cómo se limpian, validan y modelan? | [ETL_PIPELINE.md](ETL_PIPELINE.md), [DATA_MODEL.md](DATA_MODEL.md), [DATA_QUALITY.md](DATA_QUALITY.md) |
| 4. Modelado | ¿Qué métricas y métodos analíticos se aplican? | [KPI_CATALOG.md](KPI_CATALOG.md), [ANALYSIS_METHODOLOGY.md](ANALYSIS_METHODOLOGY.md) |
| 5. Evaluación | ¿Los resultados son correctos y útiles? | [TESTING.md](TESTING.md), sección de evaluación de [ANALYSIS_METHODOLOGY.md](ANALYSIS_METHODOLOGY.md) |
| 6. Presentación | ¿Cómo se comunican los resultados? | Aplicación web, [UI_DESIGN.md](UI_DESIGN.md), [POWER_BI.md](POWER_BI.md) |

En este proyecto, "modelado" (fase 4) significa modelado analítico: definición formal de
indicadores, descomposición de variaciones y detección estadística de atípicos. No se
entrenan modelos predictivos; la justificación está en [LIMITATIONS.md](LIMITATIONS.md).

## 2. De las preguntas a la evidencia

Cada pregunta de negocio se traduce a métricas, a un método y a una forma de verificar que
la respuesta es correcta.

| Pregunta | Métricas | Método | Verificación |
|----------|----------|--------|--------------|
| Q1 Unidades con más ingresos | Ingresos netos, participación | Agregación por unidad | Suma de unidades = total consolidado |
| Q2 Categorías con mejor margen | Margen bruto % | Agregación por categoría | Recalculo independiente con pandas |
| Q3 Gastos que explican desviaciones | Variación absoluta y % por cuenta | Análisis de variaciones con signo de favorabilidad | Suma de variaciones por cuenta = variación total |
| Q4 Periodos con cambios relevantes | Crecimiento intermensual e interanual, puntuación z robusta | Detección de atípicos sobre la desviación presupuestal | Evaluación contra escenarios inyectados |
| Q5 Presupuesto frente a ejecución | Presupuesto, ejecución, cumplimiento | Comparación a grano mes × unidad × cuenta | Conciliación contra el extracto presupuestal |
| Q6 Factores de rentabilidad | Puente de utilidad operativa, efectos precio, volumen y mezcla | Análisis de contribución (descomposición exacta) | Suma de efectos = variación total (prueba automatizada) |

## 3. Proceso de diseño dimensional (Kimball)

Para cada proceso de negocio se siguen los cuatro pasos de Kimball:

1. **Seleccionar el proceso de negocio:** ventas, gasto operativo y planeación presupuestal.
2. **Declarar el grano:** se fija antes de elegir dimensiones y medidas.
3. **Identificar las dimensiones:** descriptores que aplican a ese grano.
4. **Identificar los hechos:** medidas numéricas aditivas a ese grano.

### Matriz de bus

La matriz declara qué dimensiones conformadas comparte cada proceso. Dos hechos solo pueden
compararse a través de las dimensiones que tienen en común.

| Proceso (tabla de hechos) | Fecha | Unidad de negocio | Producto | Centro de costo | Cuenta |
|---------------------------|:-----:|:-----------------:|:--------:|:---------------:|:------:|
| Ventas (`fact_sales`) | día | ✔ | ✔ | | |
| Gasto operativo (`fact_operating_expenses`) | día | ✔ | | ✔ | ✔ |
| Presupuesto (`fact_budget`) | mes | ✔ | | | ✔ |

Consecuencia directa para el producto: los **filtros globales** de la aplicación son
**periodo** y **unidad de negocio**, porque son las únicas dimensiones compartidas por los
tres hechos. Los filtros por categoría o producto solo existen en los análisis de ventas.

El modelo completo, con granos, claves y restricciones, está en
[DATA_MODEL.md](DATA_MODEL.md).

## 4. Diseño de la evaluación

La evaluación responde dos preguntas distintas.

**¿Los números son correctos?** Se triangula cada indicador por tres caminos
independientes: la API (SQL sobre el modelo estrella), consultas SQL de validación escritas
aparte y un recálculo con pandas sobre los extractos de origen. Las tres cifras deben
coincidir al centavo.

**¿Los métodos analíticos detectan lo que deben?** Como los datos son sintéticos, se conoce
la verdad de fondo: el generador inyecta escenarios documentados (por ejemplo, un alza de
fletes en meses concretos). El detector de atípicos se evalúa contra esos escenarios y se
reportan exhaustividad y precisión medidas, incluidos los escenarios que **no** detecta.

Esta segunda evaluación solo es posible con datos sintéticos y es la principal razón
metodológica para usarlos. Su límite es igual de claro: mide el comportamiento del método
sobre patrones diseñados por el autor, no su desempeño sobre datos reales.

## 5. Desarrollo iterativo

El trabajo se organiza en ocho hitos, cada uno cerrado con pruebas, documentación y commits:

1. Investigación y requisitos.
2. Arquitectura y modelo dimensional.
3. Generación y validación de datos.
4. ETL y base de datos.
5. API y métricas.
6. Interfaz y visualizaciones.
7. Análisis avanzado y Power BI.
8. Pruebas, auditoría y documentación.

Las decisiones de diseño tomadas en el camino se registran en [DECISIONS.md](DECISIONS.md).
