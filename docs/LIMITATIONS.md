# Limitaciones

Este documento reúne lo que el proyecto no hace, lo que no se ha verificado y lo que no
debe concluirse de él.

## 1. Estado de cada componente

| Componente | Estado |
|------------|--------|
| Generador de datos sintéticos | Completado y verificado |
| Modelo dimensional y migraciones | Completado y verificado |
| Pipeline ETL y calidad de datos | Completado y verificado |
| API y capa analítica | Completado y verificado |
| Aplicación web | Completado y verificado (en Chromium) |
| Pruebas y CI local | Completado y verificado |
| Docker Compose | Completado y verificado (macOS, Docker Desktop 29) |
| Insumos de Power BI (consultas M, medidas DAX, tema) | Implementado, **no verificado** en Power BI |
| Informe Power BI (`.pbix`) | **Pendiente** |
| Flujo de GitHub Actions | Completado y verificado |

## 2. Lo que no se ha verificado

- **Power BI.** Power BI Desktop solo existe para Windows y el proyecto se desarrolló en
  macOS. No hay archivo `.pbix` ni capturas. Las consultas M, las medidas DAX y el tema
  nunca se han ejecutado; pueden contener errores que solo aparecerán al construir el
  informe. Los valores esperados permiten comprobarlo ([POWER_BI.md](POWER_BI.md)).
- **Otros navegadores y sistemas.** La interfaz se probó en Chromium sobre macOS. La
  instalación nativa se verificó en macOS con PostgreSQL de Homebrew; en Linux o Windows
  puede requerir ajustes en `scripts/dev_db.sh`. Docker Compose se verificó en macOS
  (arm64) con Docker Desktop 29; las imágenes son estándar de Linux, pero no se han
  construido en otro sistema anfitrión.
- **Accesibilidad real.** La auditoría es automática (`axe-core`) y no sustituye a pruebas
  con lectores de pantalla y con usuarios.

## 3. Datos

- **Todo es sintético.** La empresa no existe. Ninguna cifra sirve como referencia de un
  sector ni de un negocio real.
- **Los patrones son diseñados.** La estacionalidad, el crecimiento y los nueve escenarios
  los eligió el autor. Que un análisis los encuentre demuestra que el método funciona sobre
  esos patrones. No demuestra que funcionaría sobre datos reales, que son más ruidosos y
  menos ordenados.
- **Simplificaciones del modelo de negocio:** sin elasticidad de precio, sin efectos
  cruzados entre publicidad y demanda (salvo un escenario), sin canibalización entre
  unidades, sin autocorrelación del ruido, sin devoluciones, clientes ni facturas.
- **Calidad de datos controlada.** Los defectos inyectados son aditivos o recuperables. En
  datos reales hay defectos que destruyen información y no se pueden reparar.
- **Totales de control no independientes.** La conciliación compara el almacén con totales
  que produce el mismo generador que entrega los extractos. En un entorno real los emite un
  sistema distinto; aquí la conciliación comprueba que el ETL no pierde ni altera datos, no
  que el origen sea correcto.

## 4. Alcance funcional

- **Hasta la utilidad operativa.** No hay intereses, impuestos, balance ni flujo de caja.
- **Utilidad operativa solo por periodo y unidad de negocio.** Los gastos operativos no se
  registran por producto. No se asignan con una regla porque el resultado aparentaría una
  precisión que no existe.
- **Sin historia en las dimensiones.** Las dimensiones se sobrescriben (tipo 1); un cambio
  de atributo, como la categoría de un producto, no conserva su valor anterior.
- **Un único presupuesto.** No hay versiones, pronósticos ni reprevisiones.
- **Moneda única** y año fiscal calendario.
- **Sin pronósticos ni modelos predictivos.** Con 36 meses y patrones diseñados, un
  pronóstico solo "predeciría" lo que el generador programó. Habría sido una demostración
  sin valor.
- **Granularidad mensual** en el análisis, aunque las ventas se almacenan por día.

## 5. Métodos analíticos

- **Ninguno establece causalidad.** Las descomposiciones son identidades aritméticas: dicen
  dónde está una variación, no por qué ocurrió. Los atípicos son señales estadísticas.
- **Variación de costos variables sin separar.** La desviación del costo de ventas, los
  fletes y las comisiones mezcla el efecto del volumen vendido con el de la tarifa. Un
  presupuesto flexible los separaría y no está implementado.
- **Volumen y mezcla suman unidades heterogéneas.** El efecto precio y el total son
  robustos; el reparto entre volumen y mezcla depende de esa convención.
- **Detector de atípicos:**
  - Con 36 observaciones, el ruido puro basta para producir alguna señal en cerca del 9 %
    de las series.
  - No detecta efectos diluidos o prolongados. El alza de costos de electrónica (escenario
    S5) pasa prácticamente desapercibida; las ocho celdas que figuran como detectadas
    coinciden con otros escenarios.
  - Una de sus condiciones se añadió después de ver la primera evaluación. La evaluación con
    19 semillas adicionales muestra que la precisión se mantiene fuera de muestra (98,2 % de
    media en las señales materiales), pero esas semillas comparten los escenarios y el
    modelo de ruido del generador.
  - Que detecte los nueve escenarios depende de la realización: en 5 de 19 semillas detecta
    ocho. S2 y S9, efectos sobre gastos pequeños, son los inestables.
  - El umbral de materialidad usa el ingreso promedio de todo el historial, por lo que es algo
    más exigente al principio del periodo que al final.

  El detalle está en [ANALYSIS_METHODOLOGY.md](ANALYSIS_METHODOLOGY.md), sección 4.
- **Hallazgos por plantillas.** El panel de hallazgos arma frases con valores calculados. No
  interpreta ni prioriza por relevancia para el negocio; el orden es fijo.

## 6. Ingeniería

- **Sin autenticación ni autorización.** La API y la aplicación están pensadas para
  ejecutarse en local. No deben exponerse a una red sin añadir control de acceso.
- **Recarga completa.** El ETL trunca y recarga. Es adecuado para 10⁵ filas; con volúmenes
  mayores haría falta carga incremental.
- **Sin caché ni concurrencia.** La API es un proceso que agrega con pandas en cada
  solicitud. No se ha medido bajo carga.
- **Un solo tema visual** (oscuro) y un solo idioma en la interfaz (inglés).
- **Sin pruebas de regresión visual.** Un cambio de estilo que rompa el diseño no haría
  fallar ninguna prueba.
- **Dependencias recientes.** El proyecto usa versiones nuevas de sus herramientas
  (TypeScript 7, Vite 8, React 19). Las versiones exactas están fijadas en
  `requirements.lock` y `package-lock.json`.

## 7. Pendientes

1. Construir el informe `.pbix` en un equipo con Power BI Desktop y comprobarlo con
   `powerbi/validation/expected_values.csv`.
2. Evaluar el detector de atípicos sobre datos con otros escenarios y modelos de ruido, no
   solo con otras semillas del mismo generador.
