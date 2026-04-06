"""
chicamocha_t1_sensibilidad.py
==============================
Análisis de sensibilidad LHS / SRCC para el Río Chicamocha — Tramo T1
(CABECERA -> LA REFORMA)

Modelo base: D:/Proyecto_UB_2025/PYQ2K/data/templates/Chicamocha_T1/PlantillaBaseQ2K.xlsx
JSON base  : examples/chicamocha_t1_simulacion.json

Parámetros variados (31 en total)
-----------------------------------
  Hidráulicos (1 tramo):
    alpha_1, beta_1, alpha_2, beta_2

  Tasas cinéticas por tramo (reach_rates):
    kaaa  — reaireación       (calibrado: 2.576)
    kdc   — oxidación DBO r.  (calibrado: 1.490)
    kn    — nitrificación     (calibrado: 0.001185)
    khp   — hidrólisis P org. (calibrado: 1.096)
    kdt   — disolución detrito(calibrado: 0.108)

  Vertimientos (todos los de tipo VERTIMIENTO):
    BY-PASS-VEOLIA  Q=0.270  DBO5=263.0  — dbo5, od, temperatura
    VEOLIA          Q=0.190  DBO5= 32.75 — dbo5, od, temperatura
    URBASER         Q=0.0015 DBO5=  1.8  — dbo5, od, temperatura
    R. LA VEGA      Q=0.030  DBO5=  3.63 — dbo5, od, temperatura
    Q. HONDA        Q=0.002  DBO5= 58.0  — dbo5, od, temperatura
    R. PIEDRAS      Q=0.263  DBO5=  5.0  — dbo5, od, temperatura

  Condición de borde CABECERA (wq_data):
    caudal, dbo5, oxigeno_disuelto, temperatura, pH
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

    # ── Tasas cinéticas por tramo (reach_rates) ──────────────────────────
    # tipo="relativo": el valor muestreado MULTIPLICA al calibrado.
    # Rango [0.5, 2.0] → explorar desde la mitad hasta el doble del calibrado.
    # kaaa (reaireación): calibrado=2.576; rango físico amplio [0.5×, 3×].
    # kdc  (oxidación DBO rápida): calibrado=1.490; muy sensible → rango amplio.
    # kn   (nitrificación): calibrado=0.001185; controla NH4→NO3.
    # khp  (hidrólisis P org.): calibrado=1.096.
    # kdt  (disolución detrito): calibrado=0.108.

    ParametroSensibilidad(
        nombre    = "kaaa",
        categoria = "reach_rates",
        campo     = "kaaa",
        minimo    = 0.5,
        maximo    = 3.0,
        tipo      = "relativo",    # factor × 2.576 calibrado
    ),

    ParametroSensibilidad(
        nombre    = "kdc",
        categoria = "reach_rates",
        campo     = "kdc",
        minimo    = 0.3,
        maximo    = 3.0,
        tipo      = "relativo",    # factor × 1.490 calibrado
    ),

    ParametroSensibilidad(
        nombre    = "kn",
        categoria = "reach_rates",
        campo     = "kn",
        minimo    = 0.3,
        maximo    = 3.0,
        tipo      = "relativo",    # factor × 0.001185 calibrado
    ),

    ParametroSensibilidad(
        nombre    = "khp",
        categoria = "reach_rates",
        campo     = "khp",
        minimo    = 0.3,
        maximo    = 3.0,
        tipo      = "relativo",    # factor × 1.096 calibrado
    ),

    ParametroSensibilidad(
        nombre    = "kdt",
        categoria = "reach_rates",
        campo     = "kdt",
        minimo    = 0.3,
        maximo    = 3.0,
        tipo      = "relativo",    # factor × 0.108 calibrado
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

    # ── URBASER (PTAR pequeña, carga baja) ───────────────────────────────
    # Q=0.0015 m³/s, DBO5=1.8 mg/L — efluente tratado, rango acotado.

    ParametroSensibilidad(
        nombre        = "dbo5_urbaser",
        categoria     = "fuente",
        campo         = "dbo5",
        nombre_fuente = "URBASER TUNJA S.A E.S.P",
        minimo        = 0.5,     # mg/L — calibrado: 1.8
        maximo        = 30.0,
        tipo          = "absoluto",
    ),

    ParametroSensibilidad(
        nombre        = "od_urbaser",
        categoria     = "fuente",
        campo         = "oxigeno_disuelto",
        nombre_fuente = "URBASER TUNJA S.A E.S.P",
        minimo        = 1.0,     # mg/L — calibrado: 4.83
        maximo        = 8.0,
        tipo          = "absoluto",
    ),

    ParametroSensibilidad(
        nombre        = "temp_urbaser",
        categoria     = "fuente",
        campo         = "temperatura",
        nombre_fuente = "URBASER TUNJA S.A E.S.P",
        minimo        = 14.0,    # °C — calibrado: 18.4
        maximo        = 25.0,
        tipo          = "absoluto",
    ),

    # ── R. LA VEGA (afluente natural, aguas limpias) ──────────────────────
    # Q=0.03 m³/s, DBO5=3.63 mg/L — rango acotado por ser afluente natural.

    ParametroSensibilidad(
        nombre        = "dbo5_la_vega",
        categoria     = "fuente",
        campo         = "dbo5",
        nombre_fuente = "R. LA VEGA ",          # ojo: espacio al final
        minimo        = 1.0,     # mg/L — calibrado: 3.63
        maximo        = 15.0,
        tipo          = "absoluto",
    ),

    ParametroSensibilidad(
        nombre        = "od_la_vega",
        categoria     = "fuente",
        campo         = "oxigeno_disuelto",
        nombre_fuente = "R. LA VEGA ",
        minimo        = 3.0,     # mg/L — calibrado: 5.5
        maximo        = 9.0,
        tipo          = "absoluto",
    ),

    ParametroSensibilidad(
        nombre        = "temp_la_vega",
        categoria     = "fuente",
        campo         = "temperatura",
        nombre_fuente = "R. LA VEGA ",
        minimo        = 12.0,    # °C — calibrado: 17.3
        maximo        = 22.0,
        tipo          = "absoluto",
    ),

    # ── Q. HONDA (alta DBO5 relativa, caudal pequeño) ────────────────────
    # Q=0.002 m³/s, DBO5=58 mg/L — rango amplio en DBO5.

    ParametroSensibilidad(
        nombre        = "dbo5_honda",
        categoria     = "fuente",
        campo         = "dbo5",
        nombre_fuente = "Q. HONDA",
        minimo        = 10.0,    # mg/L — calibrado: 58
        maximo        = 200.0,
        tipo          = "absoluto",
    ),

    ParametroSensibilidad(
        nombre        = "od_honda",
        categoria     = "fuente",
        campo         = "oxigeno_disuelto",
        nombre_fuente = "Q. HONDA",
        minimo        = 0.5,     # mg/L — calibrado: 3.55
        maximo        = 7.0,
        tipo          = "absoluto",
    ),

    ParametroSensibilidad(
        nombre        = "temp_honda",
        categoria     = "fuente",
        campo         = "temperatura",
        nombre_fuente = "Q. HONDA",
        minimo        = 13.0,    # °C — calibrado: 17.6
        maximo        = 23.0,
        tipo          = "absoluto",
    ),

    # ── R. PIEDRAS (segundo mayor caudal del tramo) ───────────────────────
    # Q=0.263 m³/s, DBO5=5.0 mg/L — caudal alto, agua limpia.

    ParametroSensibilidad(
        nombre        = "dbo5_piedras",
        categoria     = "fuente",
        campo         = "dbo5",
        nombre_fuente = "R. PIEDRAS",
        minimo        = 1.0,     # mg/L — calibrado: 5.0
        maximo        = 20.0,
        tipo          = "absoluto",
    ),

    ParametroSensibilidad(
        nombre        = "od_piedras",
        categoria     = "fuente",
        campo         = "oxigeno_disuelto",
        nombre_fuente = "R. PIEDRAS",
        minimo        = 3.0,     # mg/L — calibrado: 5.51
        maximo        = 9.0,
        tipo          = "absoluto",
    ),

    ParametroSensibilidad(
        nombre        = "temp_piedras",
        categoria     = "fuente",
        campo         = "temperatura",
        nombre_fuente = "R. PIEDRAS",
        minimo        = 10.0,    # °C — calibrado: 15.5
        maximo        = 20.0,
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
        n            = 200,        # con 31 parámetros se recomienda >= 200 corridas LHS
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
