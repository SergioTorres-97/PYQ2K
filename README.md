# PYQ2K — Interfaz Python para QUAL2K

PYQ2K es una interfaz en Python para el modelo de calidad de agua **QUAL2K** (Quality 2K), cuyo motor de cálculo es un ejecutable FORTRAN. Automatiza la preparación de datos desde plantillas Excel, la ejecución del modelo, el análisis de resultados y la calibración mediante algoritmo genético.

## Modos de uso

PYQ2K se puede usar de **dos maneras**, según el nivel de interacción requerido:

---

### Modo 1 — Scripts Python (`model/`)

Ideal para correr simulaciones directamente desde la terminal, con control total sobre los parámetros. Los scripts en `model/` están listos para ejecutarse con los casos de estudio calibrados.

```bash
# Ejecutar un modelo individual
python model/modelo_vargas.py
python model/modelo_tota_chiquito.py
python model/modelo_chicamocha.py

# Ejecutar el pipeline completo (Vargas → Tramo 3S → Chicamocha)
python model/pipeline_modelo_calidad.py
```

Ver [`model/README.md`](model/README.md) para más detalle.

---

### Modo 2 — Aplicación web Django (`webapp/`)

Interfaz gráfica en el navegador para gestionar proyectos, configurar y lanzar simulaciones, y visualizar resultados sin escribir código.

```bash
# Levantar el servidor
cd webapp
python manage.py runserver 8080
```

Abre `http://localhost:8080` en el navegador.

**Funcionalidades de la webapp:**
- Gestión de proyectos y simulaciones
- Configuración de parámetros cinéticos desde formularios
- Ejecución asíncrona de simulaciones
- Visualización de gráficos y métricas KGE en el navegador
- Pipeline multi-tramo desde la interfaz

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/SergioTorres-97/PYQ2K.git
cd PYQ2K
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# Dependencias del paquete core
pip install -e .

# Dependencias adicionales para la webapp
pip install -r webapp/requirements_web.txt
```

### 3. Configurar la webapp (solo si se usa el Modo 2)

```bash
cd webapp
python manage.py migrate
python manage.py createsuperuser
```

### 4. Plantillas de datos

Los scripts de `model/` y la webapp requieren plantillas Excel (`PlantillaBaseQ2K.xlsx`) para cada tramo.
Estas plantillas **no están incluidas en el repositorio** y deben colocarse en:

```
data/templates/<nombre_tramo>/PlantillaBaseQ2K.xlsx
```

El ejecutable FORTRAN `bin/q2kfortran2_12.exe` **sí está incluido** y se copia automáticamente al directorio de trabajo al ejecutar cada simulación.

---

## Estructura del proyecto

```
PYQ2K/
├── bin/
│   └── q2kfortran2_12.exe        # Ejecutable FORTRAN (motor de cálculo)
│
├── qual2k/                        # Paquete Python principal
│   ├── core/
│   │   ├── model.py               # Q2KModel — orquestador principal
│   │   ├── config.py              # Gestión de parámetros y tasas cinéticas
│   │   ├── simulator.py           # Wrapper para ejecución del .exe
│   │   ├── calibrator.py          # Calibración con algoritmo genético (pygad)
│   │   └── calibrator_general.py  # Pipeline de calibración
│   ├── processing/
│   │   ├── data_processor.py      # Lee Excel → diccionarios
│   │   └── file_writer.py         # Escribe archivos .q2k
│   └── analysis/
│       ├── results_analyzer.py    # Parsea archivos .out
│       ├── plotter.py             # Gráficos de resultados
│       └── metricas.py            # KGE, NSE, RMSE, PBIAS
│
├── model/                         # Scripts de simulación (Modo 1)
│   ├── modelo_vargas.py
│   ├── modelo_tota_chiquito.py
│   ├── modelo_chicamocha.py
│   └── pipeline_modelo_calidad.py
│
├── webapp/                        # Aplicación web Django (Modo 2)
│   ├── apps/simulator/            # App principal
│   ├── templates/                 # HTML
│   ├── config/                    # Settings de Django
│   └── manage.py
│
├── tests/                         # Scripts de prueba y calibración
├── data/                          # Plantillas Excel (no versionadas)
│   └── templates/
└── pyproject.toml
```

---

## Flujo interno

```
PlantillaBaseQ2K.xlsx
        │
        ▼ data_processor.py
  Diccionarios Python
        │
        ▼ config.py
  Tasas cinéticas + parámetros
        │
        ▼ file_writer.py
   Archivo .q2k
        │
        ▼ simulator.py  (invoca q2kfortran2_12.exe)
   Archivo .out
        │
        ▼ results_analyzer.py
   DataFrame de resultados
        │
        ▼ plotter.py + metricas.py
  Gráficos + KGE / NSE / RMSE
```

---

## Caso de estudio: cuenca del río Chicamocha

Incluye tres modelos encadenados calibrados con datos observados:

| Tramo | Reaches | Fuentes puntuales |
|---|---|---|
| Canal Vargas | 4 | — |
| Tramo 3S (R. Tota-Chiquito) | 5 | 1 (salida Canal Vargas) |
| Río Chicamocha | 7 | 1 (salida Tramo 3S) |

La métrica de calibración principal es el **KGE (Kling-Gupta Efficiency)**, calculado sobre múltiples parámetros de calidad del agua (OD, DBO, NTK, NH₄, fósforo, *E. coli*, entre otros).

---

## Dependencias principales

| Paquete | Uso |
|---|---|
| `pandas` | Lectura de Excel y manejo de resultados |
| `numpy` | Cálculos numéricos |
| `matplotlib` / `seaborn` | Visualización |
| `openpyxl` | Lectura/escritura de archivos Excel |
| `pygad` | Algoritmo genético para calibración |
| `Django` | Interfaz web (Modo 2) |
