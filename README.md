# Modelo Q2K Python

## Descripción General

Este proyecto es una **implementación en Python del modelo de calidad del agua QUAL2K**. QUAL2K (Quality Model for Streams and Rivers version 2K) es un modelo ampliamente utilizado para simular la calidad del agua en ríos y arroyos.

El proyecto proporciona:
- Una interfaz Python para el ejecutable FORTRAN de QUAL2K
- Procesamiento automatizado de datos desde plantillas Excel
- Gestión de configuración y parámetros del modelo
- Análisis de resultados y visualización
- Calibración del modelo usando métricas KGE (Kling-Gupta Efficiency)

## Estructura del Proyecto

```
Modelo_Q2K_python/
│
├── qual2k/                          # Paquete principal
│   ├── core/                        # Funcionalidad central
│   │   ├── model.py                 # Orquestador principal Q2KModel
│   │   ├── config.py                # Gestión de configuración
│   │   └── simulator.py             # Wrapper para ejecución FORTRAN
│   │
│   ├── processing/                  # Procesamiento de datos
│   │   ├── data_processor.py        # Conversión Excel → Diccionario
│   │   └── file_writer.py           # Diccionario → archivo .q2k
│   │
│   └── analysis/                    # Análisis de resultados
│       ├── results_analyzer.py      # Parser de archivos .out
│       ├── plotter.py               # Visualización
│       └── metricas.py              # Métricas estadísticas
│
├── data/                            # Plantillas de datos
│   └── templates/
│       ├── Chicamocha/              # Caso de estudio Río Chicamocha
│       ├── Canal_vargas/
│       └── Tramo_3s/
│
└── tests/                           # Scripts de prueba
    └── uso_basico.py                # Ejemplo de uso básico
```

## Tecnologías Utilizadas

### Dependencias Principales:
- **pandas** (2.3.3): Manipulación de datos y lectura/escritura de Excel
- **numpy** (2.3.5): Cálculos numéricos y operaciones con arrays
- **matplotlib** + **seaborn**: Visualización de datos
- **openpyxl** (3.1.5): Lectura/escritura de archivos Excel
- **Python 3.13**: Características modernas de Python

### Componentes Externos:
- **Ejecutable FORTRAN QUAL2K** (q2kfortran2_12.exe): Motor de simulación
- **Plantillas Excel**: Formato estructurado de datos de entrada

## Funcionalidades Principales

### 1. Entrada y Procesamiento de Datos
- **Lectura de Plantillas Excel**: Carga datos de calidad del agua desde hojas estructuradas (REACHES, SOURCES, WQ_DATA)
- **Transformación de Datos**: Convierte datos crudos a formatos compatibles con QUAL2K:
  - DBO5 → DBO lento/rápido
  - Cálculos de especies de nitrógeno (TKN, NH4, NO3)
  - Fraccionamiento de fósforo
  - Partición de sólidos suspendidos
- **Configuración de Tramos**: Define segmentos del río con geometría hidráulica y perfiles de elevación

### 2. Configuración del Modelo
- **Gestión de Tasas Cinéticas**: Control sobre más de 60 parámetros cinéticos:
  - Ciclo del carbono (hidrólisis y descomposición de CBOD)
  - Ciclo del nitrógeno (nitrificación, denitrificación)
  - Ciclo del fósforo
  - Crecimiento/respiración de algas
  - Tasas de reaireación
- **Tasas Específicas por Tramo**: Permite personalización por cada tramo del río
- **Condiciones de Frontera**: Cabeceras, fuentes puntuales, datos meteorológicos

### 3. Generación de Archivos
- **Escritor de Archivos Q2K**: Crea archivos .q2k con formato adecuado
- **Archivo de Mensajes**: Genera message.DAT para configurar rutas de ejecución FORTRAN

### 4. Ejecución de Simulación
- **Wrapper FORTRAN**: Ejecuta el binario compilado de QUAL2K
- **Gestión de Directorios**: Maneja cambios de directorio de trabajo para la simulación

### 5. Análisis de Resultados
- **Parsing de Salidas**: Extrae datos de archivos .out conteniendo:
  - Hidráulica (caudal, velocidad, sección transversal, tiempo de viaje)
  - Perfiles de temperatura
  - 31 parámetros de calidad del agua a lo largo del río
- **Fusión de Datos**: Combina datos modelados y observados para comparación
- **Evaluación Estadística**:
  - **KGE** (Kling-Gupta Efficiency): Métrica principal de calibración
  - **NSE** (Nash-Sutcliffe Efficiency)
  - **RMSE** (Error Cuadrático Medio)
  - **PBIAS** (Sesgo Porcentual)
- **KGE Global Ponderado**: Combina múltiples KGEs de parámetros con pesos definidos por el usuario

### 6. Visualización
- **Perfiles Longitudinales**: Graficación automatizada de todos los parámetros de calidad del agua vs. distancia
- **Gráficos de Comparación**: Visualización de datos modelados vs. observados
- **Gráficos Listos para Publicación**: Formato profesional con cuadrículas, leyendas y estilos

## Cómo Usar el Proyecto

### Instalación

1. Clonar el repositorio
2. Instalar dependencias:
```bash
pip install pandas numpy matplotlib seaborn openpyxl
```

### Uso Básico

```python
from qual2k.core.model import Q2KModel

# 1. Definir información del encabezado
header_dict = {
    'nombre_rio': 'Chicamocha',
    'fecha': '01/01/2024',
    'hora': 1200,
    'zona_horaria': -5,
    'metodo_integracion': 1,
    'latitud': 6.0,
    'longitud': -73.0,
    'altitud': 2500.0
}

# 2. Crear instancia del modelo
filepath = r'data\templates\Chicamocha\PlantillaBaseQ2K.xlsx'
model = Q2KModel(filepath, header_dict)

# 3. Ejecutar flujo completo
model.cargar_plantillas()           # Cargar plantillas Excel
model.configurar_modelo()           # Configurar parámetros
model.generar_archivo_q2k()         # Generar archivo .q2k
model.ejecutar_simulacion()         # Ejecutar FORTRAN
model.analizar_resultados()         # Analizar y graficar resultados

# 4. Calcular métricas de calibración
resultados, kge_global = model.calcular_metricas_calibracion(
    parametros=['OD', 'DBO', 'NH4'],
    pesos={'OD': 0.5, 'DBO': 0.3, 'NH4': 0.2}
)

print(f"KGE Global: {kge_global}")
```

## Flujo de Trabajo

```
┌─────────────────────────────────────┐
│ 1. Preparar datos en Excel          │
│    (PlantillaBaseQ2K.xlsx)          │
│    - REACHES: Segmentos del río     │
│    - SOURCES: Fuentes puntuales     │
│    - WQ_DATA: Datos de calidad      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 2. Python procesa los datos         │
│    (data_processor.py)              │
│    - Transformación de formatos     │
│    - Conversiones de unidades       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 3. Aplicar configuración            │
│    (config.py)                      │
│    - Tasas cinéticas                │
│    - Parámetros del modelo          │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 4. Generar archivo .q2k             │
│    (file_writer.py)                 │
│    - Formato específico FORTRAN     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 5. Ejecutar simulación FORTRAN      │
│    (simulator.py)                   │
│    - Produce archivo .out           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 6. Analizar resultados              │
│    (results_analyzer.py)            │
│    - Parsear archivos .out          │
│    - Convertir a DataFrames         │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 7. Visualización y métricas         │
│    (plotter.py, metricas.py)        │
│    - Gráficos de perfiles           │
│    - Cálculo de KGE, NSE, RMSE      │
│    - Comparación modelado vs obs.   │
└─────────────────────────────────────┘
```

## Archivos Principales

### qual2k/core/model.py
Clase principal `Q2KModel` que orquesta todo el flujo de trabajo. Coordina la carga de datos, configuración, simulación y análisis.

### qual2k/core/config.py
Gestiona todos los parámetros de configuración de QUAL2K. Proporciona valores por defecto para tasas cinéticas, datos de luz, hidráulica, etc.

### qual2k/processing/data_processor.py
Convierte datos de plantillas Excel en estructuras de diccionarios compatibles con QUAL2K. Procesa tramos, fuentes puntuales, cabeceras, datos meteorológicos y de calidad del agua.

### qual2k/processing/file_writer.py
Genera archivos de entrada .q2k en formato compatible con FORTRAN. Maneja el formato de números para notación científica y valores especiales.

### qual2k/analysis/results_analyzer.py
Analiza archivos de salida .out de simulaciones QUAL2K. Extrae resultados hidráulicos, de temperatura y de calidad del agua.

### qual2k/analysis/plotter.py
Genera gráficos de calidad profesional de los resultados de simulación. Crea perfiles longitudinales para todos los parámetros de calidad del agua.

### qual2k/analysis/metricas.py
Calcula métricas de evaluación estadística: KGE, NSE, RMSE, PBIAS. Utilizado para calibración y validación del modelo.

## Caso de Estudio: Río Chicamocha

El proyecto incluye un caso de estudio completo del Río Chicamocha con:
- 70 tramos del río
- 109 fuentes puntuales
- Datos de calidad del agua observados
- Configuración meteorológica

Este caso puede usarse como plantilla para otros estudios de calidad del agua en ríos.

## Contribuciones

Este es un marco de modelación científica que une el modelo FORTRAN QUAL2K con herramientas modernas de ciencia de datos en Python, haciendo la modelación de calidad del agua más accesible y automatizada.