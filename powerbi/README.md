# Power BI

**El archivo `.pbix` no existe todavía.** Power BI Desktop solo está disponible para
Windows y el proyecto se desarrolló en macOS. Esta carpeta contiene lo necesario para
construir el informe y comprobar que sus cifras son correctas:

| Ruta | Contenido |
|------|-----------|
| `data/` | Modelo estrella en CSV. No se versiona: se genera con `make powerbi-data` |
| `queries/star_schema.pq` | Consultas Power Query (M), una por tabla |
| `measures/measures.dax` | Medidas DAX |
| `theme/financial-intelligence.json` | Tema del informe |
| `validation/expected_values.csv` | Valores que las medidas deben reproducir |

Las consultas, las medidas y el tema no se han ejecutado en Power BI. La guía de
construcción, la especificación de las páginas y el procedimiento de verificación están en
[docs/POWER_BI.md](../docs/POWER_BI.md).
