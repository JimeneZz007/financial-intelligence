# Registro de decisiones

Cada entrada recoge una decisión de diseño, las alternativas consideradas y su
consecuencia. Las decisiones no se reescriben: si una cambia, se añade una entrada nueva que
la sustituye.

## D-001 · Datos sintéticos de una empresa ficticia

- **Decisión:** usar datos generados por un proceso propio con semilla fija.
- **Alternativas:** conjuntos públicos (pocos incluyen presupuesto y gasto por cuenta con un
  grano coherente); datos reales (no disponibles y con riesgo de confidencialidad).
- **Consecuencia:** se conoce la verdad de fondo y se puede evaluar el detector de atípicos;
  a cambio, los patrones son diseñados y no prueban desempeño sobre datos reales.

## D-002 · Moneda única (USD) y año fiscal calendario

- **Decisión:** todas las cifras en dólares estadounidenses; año fiscal de enero a diciembre.
- **Alternativas:** multimoneda con tasas de cambio.
- **Consecuencia:** se evita una dimensión de moneda y la lógica de conversión, que no aporta
  a las preguntas de negocio planteadas.

## D-003 · Periodo de 36 meses (2023-01 a 2025-12)

- **Decisión:** tres años fiscales completos.
- **Alternativas:** un año (sin comparación interanual); cinco años (más volumen sin más
  capacidad analítica).
- **Consecuencia:** permite crecimiento interanual para 2024 y 2025 y deja 2023 como año base.

## D-004 · Idiomas

- **Decisión:** interfaz, código y mensajes de commit en inglés; documentación en español.
- **Motivo:** la navegación especificada para el producto está en inglés, que además es el
  idioma habitual del código; la documentación se dirige a lectores hispanohablantes.

## D-005 · Categoría de producto desnormalizada en `dim_product`

- **Decisión:** la categoría es un atributo de `dim_product`; no existe `dim_category`.
- **Alternativas:** tabla `dim_category` enlazada desde `dim_product` (copo de nieve).
- **Motivo:** Kimball recomienda dimensiones planas: una tabla menos en cada consulta, sin
  pérdida de información, y la jerarquía categoría → producto queda en una sola dimensión.
- **Consecuencia:** el catálogo de categorías se obtiene con `SELECT DISTINCT` sobre
  `dim_product`. La dependencia código → nombre de categoría ya no la garantiza una clave,
  así que la comprueba una regla de calidad del ETL.

## D-006 · Filtros globales limitados a dimensiones conformadas

- **Decisión:** los filtros globales son periodo y unidad de negocio. Categoría y producto
  son filtros locales de las vistas de ventas.
- **Motivo:** `fact_operating_expenses` y `fact_budget` no tienen dimensión producto. Filtrar
  la utilidad operativa por categoría exigiría asignar gastos a productos con una regla
  arbitraria, y el resultado aparentaría una precisión que no existe.

## D-007 · PostgreSQL local sin contenedores para el desarrollo

- **Decisión:** el entorno de desarrollo usa un clúster PostgreSQL local del proyecto
  (`scripts/dev_db.sh`). `docker-compose.yml` se entrega como alternativa.
- **Motivo:** al iniciar el proyecto, el equipo de desarrollo no tenía Docker instalado,
  y un clúster propio arranca en segundos sin depender de un daemon.
- **Consecuencia:** la ruta nativa es la principal y la que ejecuta `make ci`.
- **Actualización (2026-11-12):** con Docker instalado, `docker compose up --build` se
  ejecutó sin cambios en los archivos: las imágenes se construyen, el pipeline carga el
  almacén, las 16 consultas de validación y las 43 pruebas de extremo a extremo pasan
  contra la pila en contenedores. Ambas rutas quedan verificadas; la nativa sigue siendo la
  de desarrollo porque recarga el código al vuelo.

## D-008 · DuckDB no se utiliza

- **Decisión:** PostgreSQL resuelve todas las agregaciones.
- **Motivo:** el hecho más grande tiene del orden de 10⁵ filas; las consultas agregadas
  responden en milisegundos con los índices definidos. Un segundo motor añadiría una copia
  de los datos y una fuente más de inconsistencias sin beneficio medible.

## D-009 · Un único proyecto Python para API y pipelines

- **Decisión:** `backend/` y `pipelines/` comparten `pyproject.toml` y entorno virtual.
- **Motivo:** el pipeline de carga y la API usan las mismas definiciones de tablas
  (SQLAlchemy). Separarlos obligaría a duplicarlas o a publicar un paquete interno.

## D-010 · Agregación en SQL y análisis en pandas, sin caché

- **Decisión:** el repositorio devuelve tablas agregadas al mes y la analítica se hace en
  pandas dentro de cada solicitud. No hay caché.
- **Alternativas:** toda la lógica en SQL (las descomposiciones y la puntuación robusta son
  difíciles de leer y de probar en SQL); una caché en memoria por versión de datos.
- **Motivo:** medidas con `\timing`, las consultas base tardan entre 12 y 22 ms. Las
  funciones en pandas son puras y se prueban sin base de datos.
- **Consecuencia:** cada solicitud relee el almacén. Aceptable para uso local; habría que
  revisarlo ante concurrencia real.

## D-011 · Atípicos con puntuación z robusta sobre la variación presupuestal

- **Decisión:** puntuación z modificada (mediana y MAD) de la variación porcentual frente al
  presupuesto, por serie unidad × cuenta.
- **Alternativas:** descomposición estacional (STL) o modelos de detección no supervisados.
- **Motivo:** con 36 meses, un modelo estacional tendría tres observaciones por mes del año.
  El presupuesto ya incorpora la estacionalidad esperada, y el método se explica en una
  línea y se puede auditar a mano.
- **Consecuencia:** depende de que exista presupuesto y no ve efectos diluidos o
  persistentes (documentado con su evaluación en [ANALYSIS_METHODOLOGY.md](ANALYSIS_METHODOLOGY.md)).

## D-012 · Sin pronósticos ni modelos predictivos

- **Decisión:** la plataforma describe y descompone; no predice.
- **Motivo:** los datos son sintéticos y sus patrones están programados. Un pronóstico solo
  recuperaría la fórmula del generador y aparentaría una capacidad no demostrada.

## D-013 · Paleta de gráficos validada, sin el par verde-rojo

- **Decisión:** favorable y desfavorable se codifican con verde azulado y coral, y los
  verdes y rojos no se usan para identificar series.
- **Motivo:** la validación con simulación de daltonismo dio ΔE 4,1 para el verde y rojo
  convencionales (objetivo ≥ 8) y 11,2 para el par elegido.
- **Consecuencia:** cuatro colores de unidad solo en formas donde únicamente se tocan los
  vecinos; el margen por unidad usa múltiplos pequeños ([UI_DESIGN.md](UI_DESIGN.md)).

## D-014 · Los filtros viven en la URL

- **Decisión:** periodo, unidades y base de comparación se guardan como parámetros de la
  URL, no en un almacén de estado.
- **Motivo:** una vista se comparte con un enlace y el estado sobrevive a la recarga sin
  código adicional.

## D-015 · Tipos del cliente generados desde OpenAPI

- **Decisión:** `npm run gen:api` genera los tipos de TypeScript desde el esquema de la API.
- **Alternativas:** escribir las interfaces a mano.
- **Motivo:** un cambio en una respuesta del backend rompe la compilación del frontend en
  lugar de fallar en ejecución.
- **Consecuencia:** `openapi-typescript` se ejecuta con `npx` y no como dependencia, porque
  declara compatibilidad con TypeScript 5 y el proyecto usa la versión 7.

## D-016 · mypy estricto sin los tipos de pandas

- **Decisión:** `mypy --strict` sobre backend y pipelines, tratando pandas como no tipado.
- **Motivo:** con `pandas-stubs` el modo estricto produjo 408 errores, casi todos por
  indexaciones idiomáticas que los tipos de terceros rechazan. Sin ellos quedaron 36, todos
  corregidos.
- **Consecuencia:** el código alrededor de las tablas se verifica de forma estricta; las
  operaciones sobre las tablas, no.

## D-017 · oxlint como analizador del frontend

- **Decisión:** se conserva oxlint, el analizador que trae la plantilla actual de Vite, con
  las reglas de accesibilidad activadas.
- **Alternativas:** ESLint.
- **Motivo:** cubre las reglas necesarias sin añadir otra cadena de herramientas.

## D-018 · Recarga completa en el ETL

- **Decisión:** cada ejecución trunca y recarga el almacén en una transacción.
- **Alternativas:** carga incremental con detección de cambios.
- **Motivo:** tarda unos dos segundos y es idempotente por construcción.

## D-019 · Reglas de calidad propias

- **Decisión:** un motor de reglas propio de menos de 200 líneas.
- **Alternativas:** un marco de validación de datos externo.
- **Motivo:** una veintena de reglas simples no justifica otra dependencia, y el motor
  propio permite atribuir cada fila rechazada a una única regla.

## D-020 · Power BI sobre CSV, informe pendiente

- **Decisión:** el modelo se exporta a CSV para Power BI y el `.pbix` se deja pendiente.
- **Motivo:** Power BI Desktop no existe para macOS. Un archivo de proyecto escrito a mano
  no se podría abrir ni comprobar, así que se entregan los insumos y los valores esperados
  para verificarlo ([POWER_BI.md](POWER_BI.md)).

## D-021 · Vistas de comparación como vistas simples

- **Decisión:** `vw_actual_by_account_month` y `vw_budget_vs_actual` son vistas normales, no
  materializadas.
- **Motivo:** se resuelven en unos 20 ms; una vista materializada exigiría refrescarla tras
  cada carga y podría quedar desfasada.
