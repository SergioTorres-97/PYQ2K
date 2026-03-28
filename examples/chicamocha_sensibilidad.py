"""
chicamocha_sensibilidad.py
==========================
Análisis de sensibilidad para el Río Chicamocha.

Parámetros variados
-------------------
  Hidráulicos (reaches, todos los tramos):
    alpha_1, beta_1, alpha_2, beta_2

  Calidad de un vertimiento (By-Pass PTAR Río de Oro):
    dbo5, oxigeno_disuelto, temperatura

  Condición de borde (CABECERA en wq_data):
    caudal, dbo5, oxigeno_disuelto, temperatura, pH
"""

import sys
from pathlib import Path

# Asegurar que el paquete qual2k sea encontrado
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
# Parámetros
# ===========================================================================

parametros = [

    # ── Parámetros hidráulicos — todos los tramos ─────────────────────────
    # tipo="relativo": el valor muestreado multiplica el valor calibrado de
    # cada tramo, por lo que media=1.0 conserva la media calibrada.

    ParametroSensibilidad(
        nombre       = "alpha_1",
        categoria    = "reach",
        campo        = "alpha_1",
        distribucion = "normal",
        media        = 1.0,    # multiplicador
        std          = 0.20,   # ±20 %
        minimo       = 0.1,
        tipo         = "relativo",
    ),

    ParametroSensibilidad(
        nombre       = "beta_1",
        categoria    = "reach",
        campo        = "beta_1",
        distribucion = "normal",
        media        = 1.0,
        std          = 0.15,
        minimo       = 0.1,
        tipo         = "relativo",
    ),

    ParametroSensibilidad(
        nombre       = "alpha_2",
        categoria    = "reach",
        campo        = "alpha_2",
        distribucion = "normal",
        media        = 1.0,
        std          = 0.20,
        minimo       = 0.1,
        tipo         = "relativo",
    ),

    ParametroSensibilidad(
        nombre       = "beta_2",
        categoria    = "reach",
        campo        = "beta_2",
        distribucion = "normal",
        media        = 1.0,
        std          = 0.15,
        minimo       = 0.1,
        tipo         = "relativo",
    ),

    # ── Calidad del vertimiento By-Pass PTAR Río de Oro ──────────────────
    # Ajustar nombre_fuente al nombre exacto que aparece en el JSON base.
    # tipo="absoluto": el valor muestreado reemplaza directamente.

    ParametroSensibilidad(
        nombre        = "dbo5_bypass",
        categoria     = "fuente",
        campo         = "dbo5",
        nombre_fuente = "By-Pass PTAR Rio de Oro",
        distribucion  = "lognormal",
        media         = 150.0,   # mg/L
        std           = 0.50,    # sigma de ln(X)
        minimo        = 5.0,
        tipo          = "absoluto",
    ),

    ParametroSensibilidad(
        nombre        = "od_bypass",
        categoria     = "fuente",
        campo         = "oxigeno_disuelto",
        nombre_fuente = "By-Pass PTAR Rio de Oro",
        distribucion  = "uniform",
        minimo        = 0.5,
        maximo        = 4.0,
        media         = 2.0,
        tipo          = "absoluto",
    ),

    ParametroSensibilidad(
        nombre        = "temp_bypass",
        categoria     = "fuente",
        campo         = "temperatura",
        nombre_fuente = "By-Pass PTAR Rio de Oro",
        distribucion  = "normal",
        media         = 22.0,   # °C
        std           = 2.5,
        minimo        = 10.0,
        maximo        = 35.0,
        tipo          = "absoluto",
    ),

    # ── Condición de borde — CABECERA ────────────────────────────────────
    # nombre_estacion debe coincidir con el campo "nombre_estacion"
    # de la primera entrada en wq_data del JSON.

    ParametroSensibilidad(
        nombre          = "caudal_cabecera",
        categoria       = "cabecera",
        campo           = "caudal",
        nombre_estacion = "CABECERA",
        distribucion    = "lognormal",
        media           = 1.5,    # m³/s
        std             = 0.35,   # sigma de ln(Q)
        minimo          = 0.1,
        tipo            = "absoluto",
    ),

    ParametroSensibilidad(
        nombre          = "dbo5_cabecera",
        categoria       = "cabecera",
        campo           = "dbo5",
        nombre_estacion = "CABECERA",
        distribucion    = "normal",
        media           = 3.0,    # mg/L
        std             = 1.0,
        minimo          = 0.5,
        tipo            = "absoluto",
    ),

    ParametroSensibilidad(
        nombre          = "od_cabecera",
        categoria       = "cabecera",
        campo           = "oxigeno_disuelto",
        nombre_estacion = "CABECERA",
        distribucion    = "normal",
        media           = 7.5,    # mg/L
        std             = 1.0,
        minimo          = 2.0,
        maximo          = 12.0,
        tipo            = "absoluto",
    ),

    ParametroSensibilidad(
        nombre          = "temp_cabecera",
        categoria       = "cabecera",
        campo           = "temperatura",
        nombre_estacion = "CABECERA",
        distribucion    = "normal",
        media           = 14.0,   # °C
        std             = 2.0,
        minimo          = 8.0,
        maximo          = 22.0,
        tipo            = "absoluto",
    ),

    ParametroSensibilidad(
        nombre          = "pH_cabecera",
        categoria       = "cabecera",
        campo           = "pH",
        nombre_estacion = "CABECERA",
        distribucion    = "uniform",
        minimo          = 6.5,
        maximo          = 8.5,
        media           = 7.5,
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
        n            = 50,        # aumentar a 200+ para resultados robustos
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
        print("Tabla completa SRCC:")
        pd.set_option("display.float_format", "{:+.3f}".format)
        print(df_srcc.to_string())
