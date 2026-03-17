# model/

Scripts de ejecución de modelos QUAL2K para la cuenca del río Chicamocha.

Cada script configura y ejecuta un tramo de río usando el paquete `qual2k`,
con los parámetros calibrados mediante algoritmo genético.

## Archivos

| Script | Tramo | Reaches |
|---|---|---|
| `modelo_vargas.py` | Canal Vargas (comprobación) | 4 |
| `modelo_tota_chiquito.py` | Tramo 3S / R. Tota-Chiquito (comprobación) | 5 |
| `modelo_chicamocha.py` | Río Chicamocha (comprobación) | 7 |
| `pipeline_modelo_calidad.py` | Pipeline completo: Vargas → 3S → Chicamocha | — |

## Uso individual

Cada script de comprobación se ejecuta de forma independiente:

```bash
python model/modelo_vargas.py
python model/modelo_tota_chiquito.py
python model/modelo_chicamocha.py
```

Imprime el KGE (Kling-Gupta Efficiency) al finalizar y guarda las gráficas
en `data/templates/<tramo>/Comprobacion/resultados/`.

## Pipeline completo

`pipeline_modelo_calidad.py` encadena los tres modelos en orden, propagando
los resultados de cada tramo como condición de entrada (vertimiento) del siguiente:

```
Canal Vargas  →  Tramo 3S  →  Río Chicamocha
```

```bash
python model/pipeline_modelo_calidad.py
```

Los resultados del modelo anterior se leen del CSV de salida y se actualizan
automáticamente en la hoja `SOURCES` del Excel de plantilla del tramo siguiente.

## Requisitos

- Tener la carpeta `data/templates/` con las plantillas Excel (`PlantillaBaseQ2K.xlsx`)
- El ejecutable FORTRAN `bin/q2kfortran2_12.exe` presente en la raíz del proyecto
  (se copia automáticamente al directorio de trabajo en cada ejecución)
