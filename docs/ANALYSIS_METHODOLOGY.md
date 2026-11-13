# Metodología de análisis

Describe los métodos analíticos de la plataforma, sus supuestos y su evaluación. El código
está en [`backend/app/analytics/`](../backend/app/analytics/) y son funciones puras: reciben
tablas ya agregadas y no acceden a la base de datos, lo que permite probarlas de forma
aislada.

**Principio general.** Los análisis describen *dónde* se ubica una variación y *cuánto*
aporta cada parte. No establecen *por qué* ocurrió. Las descomposiciones son identidades
aritméticas y la detección de atípicos señala meses inusuales; ninguna de las dos prueba
una relación causal, y los textos de la aplicación están redactados en consecuencia
("mayor contribución", "superó el presupuesto").

## 1. Análisis de variaciones

Compara la ejecución con una referencia: el presupuesto o un periodo de comparación.

```
variación       = ejecución − referencia
variación %     = variación / |referencia|
impacto         = +variación  en ingresos y utilidades
                  −variación  en costos y gastos
```

- **Favorabilidad.** Depende del tipo de cuenta: gastar menos de lo presupuestado es
  favorable; vender menos, desfavorable. Las variaciones menores al 0,5 % de la referencia
  se reportan *en línea*.
- **Impacto en utilidad.** Convierte toda variación a un mismo signo. La suma de los
  impactos de las 13 cuentas es exactamente la variación de la utilidad operativa, lo que
  permite ordenar las cuentas por lo que realmente aportan a la desviación.
- **Grano de la comparación.** Mes × unidad × cuenta, el grano del presupuesto. La ejecución
  se lleva a ese grano mediante la vista `vw_actual_by_account_month`.

**Limitación.** En las cuentas variables (costo de ventas, fletes, comisiones) la variación
mezcla dos causas: se vendió más o menos de lo planeado (volumen) y cada unidad costó más o
menos (tarifa). Este análisis no las separa. Un presupuesto flexible lo haría y está fuera
del alcance.

## 2. Análisis de contribución

Tres descomposiciones exactas. En todas, la suma de las partes es igual al cambio total;
esa propiedad se comprueba con pruebas automatizadas sobre datos aleatorios, incluidos
productos que aparecen o desaparecen entre periodos.

### 2.1 Puente de utilidad operativa

Recorre el camino desde la utilidad operativa base hasta la actual:

```
UO_actual − UO_base = ΔIngresos − ΔCostos directos − Σ_g ΔGastos_g
```

donde *g* recorre los grupos de cuentas de gasto. Un aumento de costos aparece como un paso
negativo. La base puede ser el periodo de comparación o el presupuesto del mismo periodo.

### 2.2 Precio, volumen y mezcla

Descompone el cambio de ingresos netos. Para cada ítem *i*, con *q* unidades, *p* precio
neto unitario (ingreso / unidades), *Q* unidades totales y *s = q / Q*:

```
volumen_i = (Q₁ − Q₀) · s₀ᵢ · p₀ᵢ        más o menos unidades con la mezcla base
mezcla_i  = (s₁ᵢ − s₀ᵢ) · Q₁ · p₀ᵢ       desplazamiento de unidades entre ítems
precio_i  = (p₁ᵢ − p₀ᵢ) · q₁ᵢ            cambio del precio unitario realizado

Σᵢ (volumen_i + mezcla_i + precio_i) = Ingresos₁ − Ingresos₀
```

- **El ítem es el producto dentro de una unidad de negocio.** El mismo producto se vende a
  distinto precio en cada canal; si se agregaran los canales, un cambio de mezcla entre
  canales aparecería como efecto precio.
- **Productos nuevos o descontinuados.** No tienen cambio de precio; todo su efecto se
  asigna a mezcla.
- **El "precio" incluye descuentos.** Es el ingreso neto por unidad, de modo que un mayor
  descuento se registra como efecto precio negativo.

**Limitación.** La separación entre volumen y mezcla suma unidades heterogéneas (un
escritorio y una caja de bolígrafos cuentan como una unidad cada uno). El efecto precio y el
total son robustos; el reparto entre volumen y mezcla depende de esa convención.

### 2.3 Mezcla y tasa del margen bruto

Descompone el cambio del margen bruto en puntos. Para cada segmento *i* (categoría o unidad
de negocio), con *w* participación en ingresos, *m* margen del segmento y *M₀* el margen
total base:

```
tasa_i   = w₁ᵢ · (m₁ᵢ − m₀ᵢ)             el segmento se volvió más o menos rentable
mezcla_i = (w₁ᵢ − w₀ᵢ) · (m₀ᵢ − M₀)      el ingreso se movió hacia o desde ese segmento

Σᵢ (tasa_i + mezcla_i) = M₁ − M₀
```

Restar *M₀* en el término de mezcla no altera el total (las participaciones suman lo mismo
en ambos periodos) y da a cada segmento una lectura directa: ganar participación en un
segmento con margen superior al promedio aporta de forma positiva.

## 3. Detección de atípicos

### 3.1 Señal

Para cada serie unidad de negocio × cuenta (52 series, 36 meses), la variación presupuestal
porcentual del mes:

```
v_t = (ejecución_t − presupuesto_t) / presupuesto_t
```

El presupuesto ya incorpora el nivel, la tendencia y la estacionalidad esperados, por lo que
*v_t* es un residuo desestacionalizado sin necesidad de ajustar un modelo de series de
tiempo sobre solo tres años de datos.

### 3.2 Puntuación

Puntuación z modificada de Iglewicz y Hoaglin (1993):

```
z_t = 0,6745 · (v_t − mediana(v)) / MAD(v)
```

- La **mediana** y la **MAD** (mediana de las desviaciones absolutas) apenas se ven
  afectadas por los propios atípicos. La media y la desviación estándar sí: un mes extremo
  las infla y se oculta a sí mismo.
- Centrar en la mediana elimina el **sesgo sistemático de planeación** de cada serie. Un
  presupuesto siempre 2 % optimista produce un nivel, no una anomalía.
- Si MAD = 0 (más de la mitad de los meses comparten valor, como en costos fijos) se usa la
  desviación absoluta media: `z_t = (v_t − mediana) / (1,253314 · DAM)`.
- La puntuación se calcula sobre **todo el historial**, no sobre el periodo filtrado: lo
  que es típico para una serie no debe depender de lo que el usuario esté mirando.

### 3.3 Decisión

Un mes es **atípico** si cumple las tres condiciones:

1. `|z_t| > 3,5`, el umbral recomendado por los autores del método.
2. `|v_t − mediana| ≥ 1 punto porcentual`.
3. La serie tiene al menos **12 meses** con presupuesto positivo. Con menos observaciones la
   mediana y la MAD no son estimaciones fiables. Con el historial actual (36 meses) las 52
   series cumplen esta condición; protege el método si se carga un historial más corto.

Es además **material** si la variación absoluta alcanza el 0,5 % del ingreso neto mensual
promedio de la unidad de negocio. La aplicación muestra por defecto solo los atípicos
materiales y permite incluir los demás.

El promedio de ingresos que fija la materialidad se calcula sobre **todo el historial**, por
coherencia con la puntuación. Como los ingresos crecen de un año a otro, el umbral es
relativamente más exigente en los primeros meses y más laxo en los últimos. Con un
crecimiento de alrededor del 13 % anual la diferencia es moderada, pero con una tendencia
fuerte convendría un promedio móvil.

### 3.4 Límites conocidos

- **Tasa de falsos positivos con ruido puro.** Con 36 observaciones la propia MAD es
  ruidosa. En una simulación de 20 000 series gaussianas de 36 puntos, el **8,6 %** de las
  series presenta al menos una señal, muy por encima del 0,05 % por punto que sugiere la
  teoría asintótica. Con 52 series cabe esperar entre 4 y 5 con alguna señal espuria. Una
  prueba automatizada fija esta tasa.
- **Efectos persistentes.** Si un efecto dura más de la mitad del historial se convierte en
  el nivel típico y deja de ser visible.
- **Efectos diluidos.** Un efecto menor que el ruido de la serie no se detecta (ver el
  escenario S5 en la evaluación).
- **No explica.** Señala que un mes es inusual, no su causa.

## 4. Evaluación del detector

Como los datos son sintéticos, se conoce la verdad de fondo: los nueve escenarios de
[DATA_GENERATION.md](DATA_GENERATION.md) declaran las celdas (unidad, cuenta, mes) que
alteran. La evaluación se ejecuta con:

```bash
python -m pipelines.evaluation
```

y su salida se versiona en
[`evaluation/anomaly_detection.json`](evaluation/anomaly_detection.json). Una prueba
verifica que ese archivo coincide con una ejecución nueva.

**Definiciones.** Celda *primaria*: el escenario la afecta de forma directa y el detector
debería señalarla. Celda *derivada*: consecuencia mecánica (una caída de ventas reduce el
costo de ventas); señalarla es correcto pero no exigible. *Exhaustividad* = primarias
señaladas / primarias. *Precisión* = señales en celdas primarias o derivadas / señales.
*Precisión estricta* = señales en celdas primarias / señales; trata las derivadas como
errores y es la cota inferior.

### 4.1 Resultados

Sobre 1 872 celdas evaluadas, de las cuales 95 son primarias:

| Escenario | Celdas primarias | Señaladas | Materiales | Exhaustividad |
|-----------|-----------------:|----------:|-----------:|--------------:|
| S1 Pérdida de distribuidor clave | 3 | 3 | 3 | 100 % |
| S2 Campaña de adquisición | 4 | 2 | 2 | 50 % |
| S3 Remodelación de tienda | 1 | 1 | 1 | 100 % |
| S4 Nuevo contrato corporativo | 6 | 6 | 6 | 100 % |
| S5 Alza de costos de electrónica | 48 | 8 | 8 | 17 % |
| S6 Alza de fletes | 16 | 13 | 10 | 81 % |
| S7 Acuerdo legal | 1 | 1 | 1 | 100 % |
| S8 Migración de plataforma | 10 | 10 | 10 | 100 % |
| S9 Congelación de viajes | 6 | 6 | 2 | 100 % |

| Conjunto de señales | Señales | Primarias | Derivadas | Sin explicar | Exhaustividad | Precisión |
|---------------------|--------:|----------:|----------:|-------------:|--------------:|----------:|
| Todas | 80 | 50 | 17 | 13 | 52,6 % | 83,8 % |
| Solo materiales | 50 | 43 | 6 | 1 | 45,3 % | 98,0 % |

Con la definición estricta, la precisión es de 62,5 % (50 de 80) sobre todas las señales y
de 86,0 % (43 de 50) sobre las materiales.

Con esta semilla, los nueve escenarios se detectan en al menos una de sus celdas primarias.
La sección 4.5 muestra que esto no se mantiene en todas las realizaciones.

### 4.2 Lectura de los resultados

- **Lo que funciona.** Los efectos concentrados y de magnitud superior al ruido de su serie
  se detectan por completo: S1, S3, S4, S7 y S8. S8 es el caso más exigente para un método
  basado en media y desviación estándar, porque dura 10 de 36 meses; la mediana lo resiste.
- **Lo que falla: S5.** El alza de 7 % en costos de electrónica afecta al costo de ventas de
  todas las unidades durante 12 meses, pero electrónica es solo una parte del costo de cada
  unidad. A grano unidad × cuenta el efecto queda en torno a 2 o 3 puntos, del mismo orden
  que el ruido. El 17 % de la tabla **sobrestima** la detección: las 8 celdas señaladas
  coinciden con otros escenarios que mueven el costo de ventas por volumen (seis de S4, una
  de S2 y una de S3, esta última en sentido contrario). Atribuible solo a S5, la detección
  es prácticamente nula. El detector no es la herramienta adecuada para un efecto largo y
  diluido. Sí lo muestra el análisis de mezcla y tasa (sección 2.3), que en 2025 atribuye a
  electrónica la mayor caída de margen. Es la razón por la que la plataforma combina
  métodos.
- **S6 (81 %).** Se señalan 13 de 16 celdas. Las tres restantes tuvieron alzas de 20 % a
  26 % sobre presupuesto y puntuaciones z entre 3,1 y 3,3, justo por debajo del umbral.
- **S2 (50 %).** Se detecta marzo de 2025 en publicidad (+73 %) y en ingresos (+12 %). En
  abril el ruido aleatorio compensó parte del efecto en esta realización (publicidad +12 %
  frente al +35 % nominal del escenario) y ninguna de las dos celdas supera el umbral.
- **S9.** Se detecta estadísticamente en sus 6 celdas, pero solo 2 son materiales: el gasto
  de viajes es pequeño frente al ingreso de esas unidades. La regla de materialidad hace lo
  que debe.
- **Señales sin explicar (13).** Doce corresponden al arriendo de Corporate Solutions en
  2025: una línea de unos 6 400 USD mensuales cuyo presupuesto se redondea a centenas, lo
  que desplaza su variación 1,3 puntos respecto a los años anteriores, con un importe de
  unos 30 USD al mes. Es un artefacto del redondeo, no un hallazgo, y la regla de
  materialidad lo descarta. La restante (servicios profesionales de Corporate Solutions,
  octubre de 2025) es ruido de una cuenta de alta dispersión y es el único falso positivo
  material.

### 4.3 Iteración registrada

La primera versión del detector solo aplicaba el umbral `|z| > 3,5`. Su evaluación dio 92
señales con 25 sin explicar (precisión de 72,8 %): 24 de ellas eran series casi constantes
(arriendo y depreciación) donde el redondeo del presupuesto generaba puntuaciones z enormes
para diferencias de décimas de punto. Se añadió la condición de desviación mínima de 1
punto porcentual, que eliminó las 12 de depreciación y dejó las 12 de arriendo descritas
arriba. La exhaustividad no cambió.

### 4.4 Validez de la evaluación

Esta evaluación tiene límites que conviene declarar:

- **Los umbrales no son todos previos a la evaluación.** El umbral de 3,5 y la materialidad
  de 0,5 % se fijaron de antemano. La desviación mínima de 1 punto se añadió tras ver los
  primeros resultados, de modo que la precisión de 83,8 % está medida sobre los mismos datos
  que motivaron el ajuste y es optimista. La sección 4.5 lo comprueba con semillas que no se
  usaron para el ajuste.
- **Un solo conjunto de datos.** Las cifras de las secciones 4.1 a 4.3 corresponden a una
  semilla. La sección 4.5 repite la evaluación con otras 19.
- **Escenarios diseñados.** Miden el comportamiento ante patrones elegidos por el autor. No
  son una estimación del desempeño sobre datos reales.

### 4.5 Evaluación con varias semillas

Para medir cuánto dependen los resultados de una realización concreta del ruido, la
evaluación se repite sobre 20 semillas consecutivas (`20230101` a `20230120`, fijadas antes
de ver resultados):

```bash
python -m pipelines.evaluation.seeds --seeds 20   # o: make evaluate-seeds
```

Cada semilla regenera los extractos, los carga con el ETL real en la base de datos de
**pruebas** y evalúa el detector con los **mismos umbrales**. Los escenarios son idénticos
en todas; solo cambia el ruido. Las 19 semillas distintas de la del proyecto no se usaron
para fijar ningún umbral, así que también sirven de comprobación fuera de muestra del ajuste
descrito en la sección 4.3. Resultado versionado en
[`evaluation/anomaly_detection_seeds.json`](evaluation/anomaly_detection_seeds.json).

Señales materiales, 19 semillas fuera de muestra:

| Métrica | Semilla del proyecto | Media | Mínimo | Máximo |
|---------|---------------------:|------:|-------:|-------:|
| Exhaustividad | 45,3 % | 46,6 % | 42,1 % | 49,5 % |
| Precisión | 98,0 % | 98,2 % | 94,2 % | 100 % |
| Precisión estricta | 86,0 % | 84,0 % | 75,4 % | 90,9 % |
| Escenarios detectados | 9 de 9 | 8,7 | 8 | 9 |

Exhaustividad por escenario (todas las señales), mismas 19 semillas:

| Escenario | Media | Mínimo | Máximo |
|-----------|------:|-------:|-------:|
| S1, S3, S4, S7, S8 | 100 % | 100 % | 100 % |
| S6 Alza de fletes | 89 % | 69 % | 100 % |
| S9 Congelación de viajes | 66 % | 0 % | 100 % |
| S2 Campaña de adquisición | 63 % | 25 % | 100 % |
| S5 Alza de costos de electrónica | 17 % | 15 % | 21 % |

Lectura:

- **La precisión se sostiene fuera de muestra.** La media de las semillas nuevas (98,2 %) es
  igual a la de la semilla con la que se ajustó el detector. El ajuste post hoc no explica la
  precisión observada.
- **"Detecta los nueve escenarios" depende de la semilla.** En 5 de las 19 semillas una señal
  material se pierde y se detectan 8. Los escenarios inestables son S2 y S9: efectos sobre
  gastos pequeños, donde el ruido de cada realización decide si la celda supera el umbral.
- **S5 no se detecta en ninguna realización**, lo que confirma la explicación de la sección
  4.2: es una limitación del método, no de una semilla desfavorable.
- **Límite.** Todas las semillas comparten los mismos escenarios y el mismo modelo de ruido.
  La variación medida es la debida al azar del generador, no la que tendrían datos reales.

## 5. Hallazgos automáticos

El panel de hallazgos (`GET /api/v1/insights`) arma frases a partir de los cálculos
anteriores para los filtros vigentes: utilidad operativa frente a la comparación y sus
mayores contribuciones, ingresos y utilidad frente al presupuesto, la mayor desviación de
gasto en cada sentido, participación y crecimiento por unidad, márgenes por categoría,
mezcla y tasa, precio-volumen-mezcla, atípicos materiales y patrón mensual.

- Cada hallazgo incluye su **evidencia**: las cifras exactas de las que sale el texto.
- Los hallazgos **dependen del contexto**: no se ordena por unidad cuando solo hay una
  seleccionada, ni se compara cuando el periodo de comparación no tiene datos.
- No se usa ningún modelo de lenguaje ni texto escrito por escenario. Son plantillas con
  valores calculados, por lo que el resultado es determinista y reproducible.
- El generador de hallazgos no lee las definiciones de escenarios.

## 6. Referencias

- Iglewicz, B. y Hoaglin, D. C. (1993). *How to Detect and Handle Outliers*. ASQC Quality
  Press.
- Kimball, R. y Ross, M. (2013). *The Data Warehouse Toolkit* (3.ª ed.). Wiley.
- Chapman, P. et al. (2000). *CRISP-DM 1.0: Step-by-step data mining guide*. SPSS.
