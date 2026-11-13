# Verificación de reproducibilidad

Registro de una verificación completa del proyecto realizada el **2026-11-12** sobre el commit
«docs: verify the Docker Compose stack and record the results», es decir, el estado del
repositorio antes de los cambios descritos en la sección 6.
El objetivo era comprobar con evidencia, y no a partir de la documentación, que el proyecto
se instala, se ejecuta y produce las cifras que declara.

## 1. Método

La verificación se hizo con Claude (Anthropic) en una sesión distinta de la de desarrollo,
sin partir de sus conclusiones, y con revisión de la autora. No es una auditoría de un
tercero humano; su valor está en que cada resultado se puede repetir con los comandos de la
sección 7.

- Se copiaron únicamente los archivos versionados a un entorno nuevo y distinto del de
  desarrollo: **Linux (aarch64), Python 3.12.3, PostgreSQL 16, Node.js 22.23**, frente al
  macOS con Python 3.12.14 en el que se desarrolló.
- Se instalaron las dependencias desde los archivos de bloqueo (`requirements.lock`,
  `package-lock.json`) y se creó un clúster PostgreSQL vacío.
- Se ejecutó todo desde cero: generación de datos, migraciones, ETL, pruebas, API, aplicación
  web y evaluación del detector.
- Las cifras de negocio se recalcularon además con un script escrito aparte, que lee los
  extractos CSV en bruto y aplica solo las reglas de limpieza documentadas, **sin importar
  código del proyecto**.

## 2. Reproducibilidad de los datos

| Comprobación | Resultado |
|--------------|-----------|
| `python -m pipelines.generate` (semilla 20230101) | 1,7 s |
| Huella SHA-256 de los 7 extractos frente a `data/synthetic/MANIFEST.json` | 7 de 7 idénticas byte a byte |
| `MANIFEST.json` regenerado frente al versionado | Sin diferencias |
| `alembic upgrade head` | Migraciones 0001 y 0002 aplicadas |
| `python -m pipelines.etl` | 109 759 ventas, 11 159 gastos y 1 872 líneas de presupuesto cargadas; 54 reglas (44 PASS, 10 WARN, 0 FAIL) |
| Filas corregidas, rechazadas y duplicadas frente a los defectos inyectados declarados en el manifiesto | Coinciden una a una en los tres extractos |

## 3. Pruebas y análisis estático

| Verificación | Resultado |
|--------------|-----------|
| Ruff (lint y formato) | Sin incidencias |
| mypy en modo estricto | Sin incidencias (55 archivos) |
| Pytest, unitarias e integración contra PostgreSQL | 250 de 250 · cobertura de ramas 95 % |
| Consultas SQL de validación independientes | 16 de 16 sin violaciones |
| Evaluación del detector frente a `docs/evaluation/anomaly_detection.json` | Salida idéntica |
| oxlint · TypeScript estricto (`tsc -b`) · compilación de Vite | Sin incidencias |
| Vitest y Testing Library | 73 de 73 |
| Playwright contra la aplicación real (API + base de datos + web) | 43 de 43 |

Playwright se ejecutó con el navegador Chrome del sistema en lugar del Chromium que descarga
Playwright, que no estaba disponible en ese entorno. Ambos usan el mismo motor.

## 4. Cifras de negocio

Año fiscal 2025 frente a 2024. Las tres columnas se obtuvieron por caminos separados.

| Afirmación del README | API | Recálculo independiente | Estado |
|-----------------------|-----|-------------------------|--------|
| Ingresos netos 59,1 M USD, +13,4 % | 59 053 741,75 · +13,35 % | 59 053 741,75 · +13,35 % | Coincide |
| Utilidad operativa 4,0 M, +15,7 % | 3 991 969,68 · +15,70 % | 3 991 969,68 · +15,70 % | Coincide |
| Utilidad operativa 18,4 % bajo presupuesto | −18,37 % (presupuesto 4 890 100) | −18,37 % | Coincide |
| Δ ingresos = volumen + precio + mezcla | 5 029 414 + 2 426 787 − 500 024 = 6 956 178 | 5 029 414 + 2 426 787 − 500 024 = 6 956 178 | Coincide |
| Margen bruto −1,3 puntos | 32,21 % → 30,90 % | −1,31 puntos | Coincide |
| Caída del margen concentrada en electrónica | Efecto tasa de electrónica −1,27 de −1,31 puntos | — | Verificado en la API |
| 21 atípicos materiales en 2025 | 21 | — | Verificado en la API |

## 5. Lo que no se pudo verificar

- **Docker Compose.** El entorno de verificación no tenía Docker. La verificación descrita
  en el README la hizo el autor en macOS y no se repitió.
- **GitHub Actions.** No se había ejecutado nunca antes de publicar el repositorio. Su
  primera ejecución en GitHub, con los cambios de la sección 6 incluidos, pasó los tres
  trabajos (Python, web y extremo a extremo).
- **Power BI.** No hay archivo `.pbix`; Power BI Desktop no existe para macOS ni Linux. Se
  verificó que existen las 50 medidas DAX y los 116 valores esperados, no que funcionen.

## 6. Observaciones y cambios posteriores

La verificación no encontró defectos críticos. Señaló puntos menores que se corrigieron
después:

| Observación | Corrección |
|-------------|------------|
| La evaluación del detector usaba una sola semilla y uno de sus umbrales se fijó después de ver esa semilla | Nueva evaluación con 20 semillas (`make evaluate-seeds`). La precisión se mantiene fuera de muestra; los nueve escenarios se detectan en 14 de 19 semillas nuevas |
| El README afirmaba sin matices que el detector encuentra los nueve escenarios | Afirmación corregida con el resultado anterior |
| La precisión contaba como aciertos las celdas derivadas | Se reporta además la precisión estricta (86 % en las señales materiales) |
| La condición de 12 observaciones mínimas del detector no estaba documentada | Documentada en `docs/ANALYSIS_METHODOLOGY.md` |
| La base de cálculo de la materialidad no estaba discutida | Documentada, con su efecto sobre años de distinto nivel de ingresos |
| No se declaraba el tratamiento de cambios en las dimensiones | Documentado como tipo 1 en `docs/DATA_MODEL.md` y en las limitaciones |
| Faltaban en el README las secciones de modelo de datos, metodología, indicadores y trabajo futuro | Añadidas |

Después de estos cambios, la suite de Python pasó a 257 pruebas.

## 7. Cómo repetir esta verificación

```bash
make setup && make db-init && make pipeline
make ci                  # lint, tipos, pruebas, validación SQL y extremo a extremo
make evaluate            # debe reproducir docs/evaluation/anomaly_detection.json
make evaluate-seeds      # debe reproducir docs/evaluation/anomaly_detection_seeds.json
```
