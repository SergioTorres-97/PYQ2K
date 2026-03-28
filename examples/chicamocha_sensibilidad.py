"""
chicamocha_sensibilidad.py
==========================
Análisis de sensibilidad LHS / SRCC para el Río Chicamocha.

Cada parámetro solo necesita un rango plausible [minimo, maximo].
El muestreo LHS garantiza cobertura uniforme del espacio de parámetros
con un número reducido de corridas.

Parámetros variados
-------------------
  Hidráulicos (pestaña Reaches, todos los tramos):
    alpha_1  [m/s · (m³/s)^-beta_1]   coef. velocidad
    beta_1   [-]                        exp. velocidad
    alpha_2  [m · (m³/s)^-beta_2]      coef. profundidad
    beta_2   [-]                        exp. profundidad

  Calidad de un vertimiento (By-Pass PTAR Río de Oro):
    dbo5             mg/L
    oxigeno_disuelto mg/L
    temperatura      °C

  Condición de borde (pestaña WQ_Data, estación CABECERA):
    caudal           m³/s
    dbo5             mg/L
    oxigeno_disuelto mg/L
    temperatura      °C
    pH               -
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

JSON_BASE  = str(_ROOT / "examples" / "chicamocha_simulacion.json")
OUTPUT_DIR = str(_ROOT / "resultados" / "chicamocha_sensibilidad")

# ===========================================================================
# Parámetros — solo necesitás definir [minimo, maximo]
# ===========================================================================

parametros = [

    # ── Hidráulicos — todos los tramos ───────────────────────────────────
    # tipo="relativo": el valor muestreado multiplica el valor calibrado de
    # cada tramo individualmente (minimo=0.5 → 50%, maximo=2.0 → 200%).
    # Así se respeta la calibración y solo se explora la incertidumbre relativa.

    ParametroSensibilidad(
        nombre    = "alpha_1",
        categoria = "reach",
        campo     = "alpha_1",
        minimo    = 0.5,    # 50 % del valor calibrado
        maximo    = 2.0,    # 200 % del valor calibrado
        tipo      = "relativo",
    ),

    ParametroSensibilidad(
        nombre    = "beta_1",
        categoria = "reach",
        campo     = "beta_1",
        minimo    = 0.5,
        maximo    = 2.0,
        tipo      = "relativo",
    ),

    ParametroSensibilidad(
        nombre    = "alpha_2",
        categoria = "reach",
        campo     = "alpha_2",
        minimo    = 0.5,
        maximo    = 2.0,
        tipo      = "relativo",
    ),

    ParametroSensibilidad(
        nombre    = "beta_2",
        categoria = "reach",
        campo     = "beta_2",
        minimo    = 0.5,
        maximo    = 2.0,
        tipo      = "relativo",
    ),

    # ── Vertimiento: By-Pass PTAR Río de Oro ─────────────────────────────
    # Verificar que el nombre coincida exactamente con el JSON base.
    # tipo="absoluto": el valor muestreado reemplaza al del JSON.

    ParametroSensibilidad(
        nombre        = "dbo5_bypass",
        categoria     = "fuente",
        campo         = "dbo5",
        nombre_fuente = "By-Pass PTAR Rio de Oro",
        minimo        = 50.0,    # mg/L
        maximo        = 400.0,
        tipo          = "absoluto",
    ),

    ParametroSensibilidad(
        nombre        = "od_bypass",
        categoria     = "fuente",
        campo         = "oxigeno_disuelto",
        nombre_fuente = "By-Pass PTAR Rio de Oro",
        minimo        = 0.5,     # mg/L
        maximo        = 5.0,
        tipo          = "absoluto",
    ),

    ParametroSensibilidad(
        nombre        = "temp_bypass",
        categoria     = "fuente",
        campo         = "temperatura",
        nombre_fuente = "By-Pass PTAR Rio de Oro",
        minimo        = 15.0,    # °C
        maximo        = 30.0,
        tipo          = "absoluto",
    ),

    # ── Condición de borde — CABECERA ────────────────────────────────────

    ParametroSensibilidad(
        nombre          = "caudal_cabecera",
        categoria       = "cabecera",
        campo           = "caudal",
        nombre_estacion = "CABECERA",
        minimo          = 0.5,    # m³/s
        maximo          = 5.0,
        tipo            = "absoluto",
    ),

    ParametroSensibilidad(
        nombre          = "dbo5_cabecera",
        categoria       = "cabecera",
        campo           = "dbo5",
        nombre_estacion = "CABECERA",
        minimo          = 1.0,    # mg/L
        maximo          = 10.0,
        tipo            = "absoluto",
    ),

    ParametroSensibilidad(
        nombre          = "od_cabecera",
        categoria       = "cabecera",
        campo           = "oxigeno_disuelto",
        nombre_estacion = "CABECERA",
        minimo          = 4.0,    # mg/L
        maximo          = 10.0,
        tipo            = "absoluto",
    ),

    ParametroSensibilidad(
        nombre          = "temp_cabecera",
        categoria       = "cabecera",
        campo           = "temperatura",
        nombre_estacion = "CABECERA",
        minimo          = 8.0,    # °C
        maximo          = 20.0,
        tipo            = "absoluto",
    ),

    ParametroSensibilidad(
        nombre          = "pH_cabecera",
        categoria       = "cabecera",
        campo           = "pH",
        nombre_estacion = "CABECERA",
        minimo          = 6.5,
        maximo          = 8.5,
        tipo            = "absoluto",
    ),
]

# ===========================================================================
# Ejecutar
# ===========================================================================

if __name__ == "__main__":
    import pandas as pd

    df_srcc = analisis_sensibilidad(
        json_base    = JSON_BASE,
        parametros   = parametros,
        n            = 100,        # con LHS, 100 corridas suele ser suficiente
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
        print(ranking.to_string())
        print()
        print("Tabla completa SRCC  (+directa / -inversa):")
        pd.set_option("display.float_format", "{:+.3f}".format)
        print(df_srcc.to_string())
