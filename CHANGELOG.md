# Changelog

Todos los cambios relevantes del proyecto se registran en este archivo.
El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el
proyecto usa [versionado semántico](https://semver.org/lang/es/).

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
- Docker Compose y el flujo de GitHub Actions están escritos pero no se han ejecutado.
