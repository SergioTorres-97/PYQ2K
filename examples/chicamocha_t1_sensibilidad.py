"""
chicamocha_t1_sensibilidad.py
==============================
Análisis de sensibilidad LHS / SRCC para el Río Chicamocha — Tramo T1
(CABECERA → LA REFORMA)

Modelo base: D:/Proyecto_UB_2025/PYQ2K/data/templates/Chicamocha_T1/PlantillaBaseQ2K.xlsx
JSON base  : examples/chicamocha_t1_simulacion.json

Parámetros variados (13 en total)
-----------------------------------
  Hidráulicos (1 tramo, tipo="absoluto"):
    alpha_1   coef. velocidad       calibrado = 0.0958
    beta_1    exp.  velocidad       calibrado = 0.7558
    alpha_2   coef. profundidad     calibrado = 1.1037
    beta_2    exp.  profundidad     calibrado = 0.1403

  Vertimiento BY-PASS-VEOLIA (mayor carga DBO = 263 mg/L × 0.27 m³/s):
    dbo5             calibrado = 263.0  mg/L
    oxigeno_disuelto calibrado =   3.34 mg/L
    temperatura      calibrado =  20.85 °C

  Vertimiento VEOLIA (segundo en carga DBO = 32.75 mg/L × 0.19 m³/s):
    dbo5             calibrado =  32.75 mg/L
    oxigeno_disuelto calibrado =   4.44 mg/L

  Condición de borde CABECERA (wq_data):
    caudal           calibrado =   0.029 m³/s
    dbo5             calibrado =   2.5   mg/L
    oxigeno_disuelto calibrado =   6.2   mg/L
    temperatura      calibrado =  17.6   °C
    pH               calibrado =   7.1
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.sensibilidad import ParametroSensibilidad, analisis_sensibilidad

# ===========================================================================
# Rutas
# ===========================================================================

JSON_BASE  = str(_ROOT / "examples" / "chicamocha_t1_simulacion.json")
OUTPUT_DIR = str(_ROOT / "resultados" / "chicamocha_t1_sensibilidad")

# ===========================================================================
# Parámetros — rangos basados en valores calibrados y límites físicos
# ===========================================================================

parametros = [

    # ── Parámetros hidráulicos ────────────────────────────────────────────
    # Rango físico típico en QUAL2K (Manning/potencia):
    #   alpha_1 [m/s·(m³/s)^-β]:  0.03 – 0.40  (velocidad)
    #   beta_1  [-]:               0.35 – 0.95  (exp. velocidad, < 1)
    #   alpha_2 [m·(m³/s)^-β]:    0.30 – 2.50  (profundidad)
    #   beta_2  [-]:               0.05 – 0.45  (exp. profundidad)
    # tipo="absoluto": los rangos son valores directos, no multiplicadores.

    ParametroSensibilidad(
        nombre    = "alpha_1",
        categoria = "reach",
        campo     = "alpha_1",
        minimo    = 0.03,    # valor calibrado: 0.0958
        maximo    = 0.40,
        tipo      = "absoluto",
    ),

    ParametroSensibilidad(
        nombre    = "beta_1",
        categoria = "reach",
        campo     = "beta_1",
        minimo    = 0.35,    # valor calibrado: 0.7558
        maximo    = 0.95,
        tipo      = "absoluto",
    ),

    ParametroSensibilidad(
        nombre    = "alpha_2",
        categoria = "reach",
        campo     = "alpha_2",
        minimo    = 0.30,    # valor calibrado: 1.1037
        maximo    = 2.50,
        tipo      = "absoluto",
    ),

    ParametroSensibilidad(
        nombre    = "beta_2",
        categoria = "reach",
        campo     = "beta_2",
        minimo    = 0.05,    # valor calibrado: 0.1403
        maximo    = 0.45,
        tipo      = "absoluto",
    ),

    # ── BY-PASS-VEOLIA (mayor carga DBO del tramo) ────────────────────────
    # Es el vertimiento más crítico: DBO5 = 263 mg/L, Q = 0.27 m³/s
    # Rango amplio porque es un bypass (sin tratamiento): puede variar mucho.

    ParametroSensibilidad(
        nombre        = "dbo5_bypass",
        categoria     = "fuente",
        campo         = "dbo5",
        nombre_fuente = "BY-PASS-VEOLIA AGUAS DE TUNJA S.A. E.S.P.",
        minimo        = 50.0,    # mg/L — valor calibrado: 263
        maximo        = 600.0,
        tipo          = "absoluto",
    ),

    ParametroSensibilidad(
        nombre        = "od_bypass",
        categoria     = "fuente",
        campo         = "oxigeno_disuelto",
        nombre_fuente = "BY-PASS-VEOLIA AGUAS DE TUNJA S.A. E.S.P.",
        minimo        = 0.5,     # mg/L — valor calibrado: 3.34
        maximo        = 6.0,
        tipo          = "absoluto",
    ),

    ParametroSensibilidad(
        nombre        = "temp_bypass",
        categoria     = "fuente",
        campo         = "temperatura",
        nombre_fuente = "BY-PASS-VEOLIA AGUAS DE TUNJA S.A. E.S.P.",
        minimo        = 15.0,    # °C — valor calibrado: 20.85
        maximo        = 30.0,
        tipo          = "absoluto",
    ),

    # ── VEOLIA (PTAR tratada, segunda en carga DBO) ───────────────────────
    # Rango más acotado: es efluente tratado, DBO5 controlada.

    ParametroSensibilidad(
        nombre        = "dbo5_veolia",
        categoria     = "fuente",
        campo         = "dbo5",
        nombre_fuente = "VEOLIA AGUAS DE TUNJA S.A. E.S.P.",
        minimo        = 5.0,     # mg/L — valor calibrado: 32.75
        maximo        = 150.0,
        tipo          = "absoluto",
    ),

    ParametroSensibilidad(
        nombre        = "od_veolia",
        categoria     = "fuente",
        campo         = "oxigeno_disuelto",
        nombre_fuente = "VEOLIA AGUAS DE TUNJA S.A. E.S.P.",
        minimo        = 1.0,     # mg/L — valor calibrado: 4.44
        maximo        = 8.0,
        tipo          = "absoluto",
    ),

    # ── Condición de borde — CABECERA ─────────────────────────────────────
    # Q = 0.029 m³/s es un caudal muy bajo (cabecera alta).
    # Rango basado en variabilidad estacional típica del río.

    ParametroSensibilidad(
        nombre          = "caudal_cabecera",
        categoria       = "cabecera",
        campo           = "caudal",
        nombre_estacion = "CABECERA",
        minimo          = 0.005,  # m³/s — valor calibrado: 0.029
        maximo          = 0.150,
        tipo            = "absoluto",
    ),

    ParametroSensibilidad(
        nombre          = "dbo5_cabecera",
        categoria       = "cabecera",
        campo           = "dbo5",
        nombre_estacion = "CABECERA",
        minimo          = 0.5,    # mg/L — valor calibrado: 2.5
        maximo          = 8.0,
        tipo            = "absoluto",
    ),

    ParametroSensibilidad(
        nombre          = "od_cabecera",
        categoria       = "cabecera",
        campo           = "oxigeno_disuelto",
        nombre_estacion = "CABECERA",
        minimo          = 4.0,    # mg/L — valor calibrado: 6.2
        maximo          = 9.0,
        tipo            = "absoluto",
    ),

    ParametroSensibilidad(
        nombre          = "temp_cabecera",
        categoria       = "cabecera",
        campo           = "temperatura",
        nombre_estacion = "CABECERA",
        minimo          = 12.0,   # °C — valor calibrado: 17.6
        maximo          = 22.0,
        tipo            = "absoluto",
    ),

    ParametroSensibilidad(
        nombre          = "pH_cabecera",
        categoria       = "cabecera",
        campo           = "pH",
        nombre_estacion = "CABECERA",
        minimo          = 6.5,    # valor calibrado: 7.1
        maximo          = 8.5,
        tipo            = "absoluto",
    ),
]

# ===========================================================================
# Resumen de la configuración
# ===========================================================================

def _imprimir_resumen():
    print("=" * 70)
    print("ANÁLISIS DE SENSIBILIDAD — CHICAMOCHA T1  (CABECERA → LA REFORMA)")
    print("=" * 70)
    print(f"{'Parámetro':<30} {'Categoría':<10} {'Campo':<22} {'[min, max]'}")
    print("-" * 70)
    for p in parametros:
        extra = ""
        if p.nombre_fuente:
            extra = p.nombre_fuente[:25]
        elif p.nombre_estacion:
            extra = p.nombre_estacion
        print(f"  {p.nombre:<28} {p.categoria:<10} {p.campo:<22} [{p.minimo}, {p.maximo}]")
    print(f"\nTotal: {len(parametros)} parámetros")
    print("=" * 70)

# ===========================================================================
# Ejecutar
# ===========================================================================

if __name__ == "__main__":
    import pandas as pd

    _imprimir_resumen()

    df_srcc = analisis_sensibilidad(
        json_base    = JSON_BASE,
        parametros   = parametros,
        n            = 100,        # 100 corridas LHS
        output_dir   = OUTPUT_DIR,
        seed         = 42,
        n_workers    = 4,
        limpiar_runs = True,
    )

    if not df_srcc.empty:
        print("\n" + "=" * 70)
        print("RANKING DE SENSIBILIDAD  (|SRCC| promedio por parámetro)")
        print("=" * 70)
        ranking = df_srcc.abs().mean(axis=1).sort_values(ascending=False)
        for param, srcc_medio in ranking.items():
            barra = "█" * int(srcc_medio * 30)
            print(f"  {param:<30} {srcc_medio:.3f}  {barra}")

        print("\nTabla completa SRCC  (+directa / -inversa):")
        pd.set_option("display.float_format", "{:+.3f}".format)
        print(df_srcc.to_string())

        print(f"\nResultados en: {OUTPUT_DIR}")
