"""
pipeline_modelo_calidad.py
==========================
Pipeline secuencial de calidad de agua para la cuenca del río Chicamocha.

Orden de ejecución:
    1. Canal Vargas        → calibración y exportación de resultados
    2. Tramo 3S            → recibe vertimiento del Canal Vargas
    3. Río Chicamocha      → recibe vertimiento del Tramo 3S (R. Chiquito)

Cada modelo se ejecuta, analiza y sus resultados se propagan al siguiente
tramo como condición de entrada (vertimiento aguas arriba).
"""

import sys
from pathlib import Path

# Asegura que el paquete raíz del proyecto esté en el path
sys.path.insert(0, str(Path(__file__).parent.parent))

import warnings
import pandas as pd
from qual2k.core.model import Q2KModel

warnings.filterwarnings('ignore')

# ─── RUTAS BASE ───────────────────────────────────────────────────────────────

BASE = Path(__file__).parent.parent

# ─── CONFIGURACIÓN COMPARTIDA ─────────────────────────────────────────────────

# Parámetros de encabezado comunes a todos los modelos
HEADER_BASE = {
    "version":       "v2.12",
    "xmon":          6,
    "xday":          27,
    "xyear":         2012,
    "timezonehour":  -6,
    "pco2":          0.000347,
    "dtuser":        4.16666666666667E-03,
    "tf":            5,
    "IMeth":         "Euler",
    "IMethpH":       "Brent",
}

# Mapeo entre columnas del CSV de resultados y columnas del Excel de vertimientos
MAPEO_COLUMNAS = {
    'flow':                   'CAUDAL',
    'water_temp_c':           'TEMPERATURA',
    'conductivity':           'CONDUCTIVIDAD',
    'total_suspended_solids': 'SST',
    'dissolved_oxygen':       'OXIGENO_DISUELTO',
    'carbonaceous_bod_fast':  'DBO5',
    'total_kjeldahl_nitrogen':'NTK',
    'ammonium':               'NITROGENO_AMONIACAL',
    'nitrite':                'NITRITOS',
    'nitrate':                'NITRATOS',
    'total_phosphorus':       'FOSFORO_TOTAL',
    'inorganic_phosphorus':   'ORTOFOSFATOS',
    'pathogen':               'E_COLI',
    'alkalinity':             'ALCALINIDAD',
    'pH':                     'pH',
}

# Columnas expresadas en µg/L en el CSV → se convierten a mg/L dividiendo por 1000
COLUMNAS_UG_A_MG = {
    'total_kjeldahl_nitrogen', 'ammonium', 'nitrite',
    'nitrate', 'total_phosphorus', 'inorganic_phosphorus',
}


# ─── FUNCIONES AUXILIARES ─────────────────────────────────────────────────────

def actualizar_vertimiento_desde_resultados(
        filepath_resultados: str,
        filepath_excel_vertimientos: str,
        nombre_vertimiento: str,
        filepath_excel_salida: str = None,
        fila_resultado: int = 0,
) -> None:
    """
    Actualiza los valores de un vertimiento en el Excel de entrada
    con los resultados exportados por el modelo QUAL2K.

    Parámetros
    ----------
    filepath_resultados : str
        Ruta al archivo CSV con los resultados del modelo anterior.
    filepath_excel_vertimientos : str
        Ruta al archivo Excel cuya hoja SOURCES se actualizará.
    nombre_vertimiento : str
        Nombre del vertimiento a actualizar (columna NOMBRE_VERTIMIENTO).
    filepath_excel_salida : str, opcional
        Ruta de salida del Excel. Si es None, se sobreescribe el original.
    fila_resultado : int, opcional
        Índice de la fila del CSV a utilizar (por defecto la primera, índice 0).
    """
    # --- Leer y limpiar el CSV de resultados ---
    df_resultados = pd.read_csv(filepath_resultados, header=0, dtype=str)
    for col in df_resultados.columns:
        df_resultados[col] = (
            df_resultados[col].astype(str).str.strip().str.replace(',', '.')
        )
        df_resultados[col] = pd.to_numeric(df_resultados[col], errors='coerce')

    resultados = df_resultados.iloc[fila_resultado]

    # --- Leer el Excel de vertimientos ---
    todas_las_hojas = pd.read_excel(filepath_excel_vertimientos, sheet_name=None)
    excel_vertimientos = todas_las_hojas['SOURCES'].copy()

    # --- Actualizar la fila del vertimiento indicado ---
    idx = excel_vertimientos[
        excel_vertimientos['NOMBRE_VERTIMIENTO'] == nombre_vertimiento
    ].index

    if len(idx) > 0:
        for col_csv, col_excel in MAPEO_COLUMNAS.items():
            if col_csv in resultados.index and col_excel in excel_vertimientos.columns:
                valor = resultados[col_csv] if pd.notna(resultados[col_csv]) else None
                if valor is not None and col_csv in COLUMNAS_UG_A_MG:
                    valor = valor / 1000.0  # µg/L → mg/L
                excel_vertimientos.at[idx[0], col_excel] = valor

        # Asegurar tipo float en columnas de calidad
        for col in MAPEO_COLUMNAS.values():
            if col in excel_vertimientos.columns:
                excel_vertimientos[col] = excel_vertimientos[col].astype(float)

    # --- Guardar el Excel actualizado ---
    todas_las_hojas['SOURCES'] = excel_vertimientos
    ruta_salida = filepath_excel_salida or filepath_excel_vertimientos
    with pd.ExcelWriter(ruta_salida, engine='openpyxl') as writer:
        for nombre_hoja, df_hoja in todas_las_hojas.items():
            df_hoja.to_excel(writer, sheet_name=nombre_hoja, index=False)
def _header(rivname: str, filepath: str) -> dict:
    """Construye el diccionario de encabezado para un modelo dado su nombre y directorio."""
    return {
        **HEADER_BASE,
        "rivname":  rivname,
        "filename": rivname,
        "filedir":  filepath,
        "applabel": f"{rivname} (6/27/2012)",
    }
def _separador(titulo: str) -> None:
    """Imprime un separador visual en consola."""
    print('=' * 70)
    print(titulo)


# ─── MODELOS ──────────────────────────────────────────────────────────────────

def ejecutar_canal_vargas() -> str:
    """
    Ejecuta el modelo QUAL2K para el Canal Vargas.

    Retorna
    -------
    str
        Ruta al CSV de resultados, que se usará como entrada del Tramo 3S.
    """
    _separador('MODELO CANAL VARGAS')

    filepath = str(BASE / 'data/templates/Canal_vargas')
    model = Q2KModel(filepath, _header('Canal_vargas', filepath))
    model.cargar_plantillas()
    n = len(model.data_reaches)

    model.configurar_modelo(
        reach_rates_custom=model.config.generar_reach_rates_custom(
            n=n,
            kaaa_list=[4.204655, 4.474614, 3.208331, 1.218291],
            khc_list= [None] * n,
            kdcs_list=[None] * n,
            kdc_list= [1.996939, 0.039535, 0.012085, 1.865734],
            khn_list= [None] * n,
            kn_list=  [0.008738, 0.001458, 0.001016, 0.009821],
            ki_list=  [None] * n,
            khp_list= [0.113002, 0.544096, 0.225615, 1.329820],
            kdt_list= [1.988082, 1.982065, 1.995186, 1.132503],
        ),
        q_cabecera=2.3148E-06,
    )

    model.generar_archivo_q2k()
    model.ejecutar_simulacion()
    model.analizar_resultados(generar_graficas=True)
    _, kge = model.calcular_metricas_calibracion()
    print(f'KGE Canal Vargas: {kge}')

    return filepath + '/resultados/Canal_vargas.csv'


def ejecutar_tramo_3s(ruta_resultados_vargas: str) -> str:
    """
    Ejecuta el modelo QUAL2K para el Tramo 3S.

    Primero propaga los resultados del Canal Vargas como vertimiento
    de entrada ('CANAL VARGAS') en la plantilla de este tramo.

    Parámetros
    ----------
    ruta_resultados_vargas : str
        CSV de resultados del modelo Canal Vargas.

    Retorna
    -------
    str
        Ruta al CSV de resultados, que se usará como entrada del río Chicamocha.
    """
    _separador('MODELO TRAMO 3S')

    filepath = str(BASE / 'data/templates/Tramo_3s')

    actualizar_vertimiento_desde_resultados(
        filepath_resultados=ruta_resultados_vargas,
        filepath_excel_vertimientos=filepath + '/PlantillaBaseQ2K.xlsx',
        nombre_vertimiento='CANAL VARGAS',
    )

    model = Q2KModel(filepath, _header('Tramo_3s', filepath))
    model.cargar_plantillas()
    n = len(model.data_reaches)

    model.configurar_modelo(
        reach_rates_custom=model.config.generar_reach_rates_custom(
            n=n,
            kaaa_list=[4.471859, 4.350509, 4.401205, 1.652704, 0.695124],
            khc_list= [None] * n,
            kdcs_list=[None] * n,
            kdc_list= [1.661489, 0.014624, 0.038643, 0.114896, 0.132706],
            khn_list= [None] * n,
            kn_list=  [0.001894, 0.002043, 0.001480, 0.001737, 0.015219],
            ki_list=  [None] * n,
            khp_list= [0.775170, 0.190168, 0.115224, 1.724441, 1.419498],
            kdt_list= [0.035449, 0.348187, 1.834888, 1.920325, 1.972559],
        ),
        q_cabecera=4.1666E-06,
    )

    model.generar_archivo_q2k()
    model.ejecutar_simulacion()
    model.analizar_resultados(generar_graficas=True)
    _, kge = model.calcular_metricas_calibracion()
    print(f'KGE Tramo 3s: {kge}')

    return filepath + '/resultados/Tramo_3s.csv'


def ejecutar_chicamocha(ruta_resultados_tramo3s: str) -> None:
    """
    Ejecuta el modelo QUAL2K para el Río Chicamocha.

    Primero propaga los resultados del Tramo 3S como vertimiento
    de entrada ('R. CHIQUITO') en la plantilla de Chicamocha.

    Parámetros
    ----------
    ruta_resultados_tramo3s : str
        CSV de resultados del modelo Tramo 3S.
    """
    _separador('MODELO RÍO CHICAMOCHA')

    filepath = str(BASE / 'data/templates/Chicamocha')

    actualizar_vertimiento_desde_resultados(
        filepath_resultados=ruta_resultados_tramo3s,
        filepath_excel_vertimientos=filepath + '/PlantillaBaseQ2K.xlsx',
        nombre_vertimiento='R. CHIQUITO',
    )

    model = Q2KModel(filepath, _header('Chicamocha', filepath))
    model.cargar_plantillas()
    n = len(model.data_reaches)

    model.configurar_modelo(
        reach_rates_custom=model.config.generar_reach_rates_custom(
            n=n,
            kaaa_list=[3.268083, 3.996890, 3.915864, 3.937074, 4.382293, 4.000035, 4.149867],
            khc_list= [None] * n,
            kdcs_list=[None] * n,
            kdc_list= [0.833527, 0.600246, 1.871435, 0.675586, 0.032112, 0.094995, 0.162900],
            khn_list= [None] * n,
            kn_list=  [0.000486, 0.000438, 0.000151, 0.000178, 0.000142, 0.000375, 0.000482],
            ki_list=  [None] * n,
            khp_list= [1.584913, 1.329111, 1.768667, 1.835800, 0.349561, 0.609004, 0.507536],
            kdt_list= [0.085480, 0.204695, 0.177963, 0.093597, 0.045421, 0.047896, 0.415943],
        ),
        q_cabecera=1.053E-06,
    )

    model.config.actualizar_rates(kpath=0.05, aPath=0.001)
    model.generar_archivo_q2k()
    model.ejecutar_simulacion()
    model.analizar_resultados(generar_graficas=True)
    _, kge = model.calcular_metricas_calibracion()
    print(f'KGE Chicamocha: {kge}')


# ─── PUNTO DE ENTRADA ─────────────────────────────────────────────────────────

def main() -> None:
    """Ejecuta el pipeline completo en orden: Canal Vargas → Tramo 3S → Chicamocha."""
    ruta_vargas   = ejecutar_canal_vargas()
    ruta_tramo3s  = ejecutar_tramo_3s(ruta_vargas)
    ejecutar_chicamocha(ruta_tramo3s)


if __name__ == '__main__':
    main()
