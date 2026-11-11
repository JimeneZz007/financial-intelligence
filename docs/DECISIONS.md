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
- **Motivo:** el equipo de desarrollo no tiene Docker instalado.
- **Consecuencia:** la ruta nativa está verificada; la ruta con Docker Compose está
  implementada pero **no verificada** (ver [LIMITATIONS.md](LIMITATIONS.md)).

## D-008 · DuckDB no se utiliza

- **Decisión:** PostgreSQL resuelve todas las agregaciones.
- **Motivo:** el hecho más grande tiene del orden de 10⁵ filas; las consultas agregadas
  responden en milisegundos con los índices definidos. Un segundo motor añadiría una copia
  de los datos y una fuente más de inconsistencias sin beneficio medible.

## D-009 · Un único proyecto Python para API y pipelines

- **Decisión:** `backend/` y `pipelines/` comparten `pyproject.toml` y entorno virtual.
- **Motivo:** el pipeline de carga y la API usan las mismas definiciones de tablas
  (SQLAlchemy). Separarlos obligaría a duplicarlas o a publicar un paquete interno.
