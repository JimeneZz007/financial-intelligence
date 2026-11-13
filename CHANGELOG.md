# Changelog

Todos los cambios relevantes del proyecto se registran en este archivo.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el
proyecto usa [versionado semántico](https://semver.org/lang/es/).

## [Sin publicar]

### Verificado

- GitHub Actions, ejecutado por primera vez al publicar el repositorio: los trabajos de
  Python, web y extremo a extremo pasan.
- Docker Compose, ejecutado por primera vez con Docker Desktop 29 en macOS: las imágenes se
  construyen, el pipeline carga el almacén, las 16 consultas de validación y las 43 pruebas
  de extremo a extremo pasan contra la pila en contenedores. Documentación actualizada en
  consecuencia.

### Añadido

- Evaluación del detector de atípicos con 20 semillas (`make evaluate-seeds`): mide la
  variabilidad de exhaustividad y precisión, comprueba fuera de muestra el umbral añadido
  tras la primera evaluación y reporta la precisión estricta. Resultados en
  `docs/evaluation/anomaly_detection_seeds.json`.
- `AUDIT.md`: verificación de reproducibilidad de todas las cifras desde un entorno limpio.
- README: secciones de modelo de datos, metodología, indicadores, resultados y trabajo
  futuro.
- La configuración de Playwright acepta `E2E_WEB_URL` y `E2E_API_URL` para ejecutar la
  misma suite contra otro despliegue; `make e2e-docker` la lanza contra Docker Compose.

### Corregido

- El README afirmaba sin matices que el detector encuentra los nueve escenarios; con otras
  semillas encuentra ocho en 5 de 19 casos. Afirmación corregida.
- Documentados la condición de 12 observaciones mínimas del detector, la base de cálculo
  de la materialidad y el tratamiento tipo 1 de las dimensiones.

## [0.1.0] - 2026-11-12

Primera versión funcional. Sin publicar.

### Añadido

- **Datos sintéticos.** Generador reproducible (semilla fija) de ventas diarias, libro de
  gastos, presupuesto mensual y datos maestros de una empresa ficticia, con nueve
  escenarios documentados, defectos de calidad controlados y un manifiesto con huellas
  SHA-256 y totales de control.
- **Modelo dimensional.** Esquema estrella en PostgreSQL con tres hechos, cinco
  dimensiones conformadas, restricciones de grano y de negocio, vistas de comparación
  entre presupuesto y ejecución, y migraciones Alembic.
- **Pipeline ETL.** Estandarización, validación por fila con cuarentena, deduplicación,
  carga transaccional con `COPY`, conciliación con los totales de control, reversión ante
  fallos y auditoría de cada ejecución. Dieciséis consultas SQL de validación
  independientes.
- **Capa analítica.** Fórmulas de KPI, análisis de variaciones con favorabilidad, puente de
  utilidad operativa, descomposición en precio, volumen y mezcla, efectos de mezcla y tasa
  sobre el margen, y detección de atípicos con puntuación z robusta.
- **API.** Veinte endpoints de solo lectura con filtros globales validados, respuestas
  tipadas, paginación, exportación CSV y documentación OpenAPI.
- **Aplicación web.** Ocho vistas con filtros globales en la URL, vista de tabla para cada
  gráfico, hallazgos con su evidencia, estados de carga, vacío y error, y diseño adaptable.
- **Insumos de Power BI.** Consultas Power Query, cincuenta medidas DAX, tema y 116 valores
  esperados para verificar el informe.
- **Evaluación.** Script que puntúa el detector de atípicos contra los escenarios
  inyectados; resultados versionados.
- **Pruebas.** 250 pruebas de Python (cobertura de 95 %), 73 de componentes y 43 de extremo
  a extremo, con auditoría de accesibilidad.
- **Infraestructura.** Clúster PostgreSQL local del proyecto, `Makefile`, CI local, flujo
  de GitHub Actions y Docker Compose.
- **Documentación.** Dieciocho documentos, con capturas reales de la aplicación.

### Corregido

- El detector de atípicos señalaba como anómalas diferencias de décimas de punto en series
  casi constantes; ahora exige una desviación mínima de un punto porcentual.
- Al seleccionar dos unidades de negocio muy seguidas, la segunda selección sobrescribía la
  primera.
- Texto tenue y celdas de mapas de calor con contraste inferior a 4,5:1.
- Controles que ensanchaban la página en pantallas de teléfono.
- Precisión desigual de las cifras en una misma fila o columna.

### Pendiente

- El informe Power BI (`.pbix`): requiere Power BI Desktop, no disponible en macOS. Las
  consultas M, las medidas DAX y el tema no se han ejecutado en Power BI.
- Docker Compose y el flujo de GitHub Actions están escritos pero no se han ejecutado
  (Docker Compose quedó verificado después; ver «Sin publicar»).
