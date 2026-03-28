"""
sensibilidad.py  –  Análisis de sensibilidad LHS / SRCC para QUAL2K
====================================================================

Muestrea N combinaciones de parámetros usando Latin Hypercube Sampling (LHS),
corre QUAL2K en paralelo y calcula el SRCC (Spearman Rank Correlation
Coefficient) entre cada parámetro y la media espacial de cada variable simulada.

¿Por qué LHS?
-------------
Con Monte Carlo puro los valores se agrupan aleatoriamente, dejando zonas del
espacio de parámetros sin cubrir. LHS divide el rango de cada parámetro en N
intervalos equiprobables y toma exactamente una muestra por intervalo, rotando
aleatoriamente entre parámetros. El resultado:
  - Cobertura uniforme garantizada con N mucho menor que Monte Carlo puro.
  - SRCC más estable con 50–100 corridas en vez de 200–500.

Distribución asumida: uniforme [minimo, maximo]
-----------------------------------------------
Cuando no se conoce la distribución real de un parámetro, la distribución
uniforme es la hipótesis más honesta: solo se asume que el parámetro está
dentro de un rango plausible, sin dar más peso a ningún valor interior.

Parámetros soportados
---------------------
  categoria="reach"    → alpha_1, beta_1, alpha_2, beta_2
  categoria="fuente"   → dbo5, oxigeno_disuelto, temperatura, pH, caudal
                         (de un vertimiento identificado por nombre_fuente)
  categoria="cabecera" → caudal, dbo5, oxigeno_disuelto, temperatura, pH
                         (en la estación de cabecera de wq_data)

Uso básico
----------
    from scripts.sensibilidad import ParametroSensibilidad, analisis_sensibilidad

    parametros = [
        ParametroSensibilidad(
            nombre    = "alpha_1",
            categoria = "reach",
            campo     = "alpha_1",
            minimo    = 0.10,
            maximo    = 0.80,
            tipo      = "absoluto",
        ),
        ParametroSensibilidad(
            nombre        = "dbo5_bypass",
            categoria     = "fuente",
            campo         = "dbo5",
            nombre_fuente = "By-Pass PTAR Rio de Oro",
            minimo        = 50.0,
            maximo        = 400.0,
            tipo          = "absoluto",
        ),
        ParametroSensibilidad(
            nombre          = "caudal_cabecera",
            categoria       = "cabecera",
            campo           = "caudal",
            nombre_estacion = "CABECERA",
            minimo          = 0.5,
            maximo          = 5.0,
            tipo            = "absoluto",
        ),
    ]

    df_srcc = analisis_sensibilidad(
        json_base    = "examples/chicamocha_simulacion.json",
        parametros   = parametros,
        n            = 100,
        output_dir   = "resultados/sensibilidad",
        n_workers    = 4,
        limpiar_runs = True,
    )
"""

from __future__ import annotations

import copy
import json
import multiprocessing as mp
import os
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, linregress
from scipy.stats.qmc import LatinHypercube

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ---------------------------------------------------------------------------
# Campos permitidos por categoría
# ---------------------------------------------------------------------------

_CAMPOS_REACH    = {"alpha_1", "beta_1", "alpha_2", "beta_2"}
_CAMPOS_FUENTE   = {"dbo5", "oxigeno_disuelto", "temperatura", "pH", "caudal"}
_CAMPOS_CABECERA = {"caudal", "dbo5", "oxigeno_disuelto", "temperatura", "pH"}

# ---------------------------------------------------------------------------
# Variables de salida de QUAL2K incluidas en el análisis
# ---------------------------------------------------------------------------

_VARIABLES_SALIDA: Dict[str, str] = {
    "dissolved_oxygen":      "Oxígeno Disuelto (mg/L)",
    "carbonaceous_bod_fast": "DBO Rápida (mg/L)",
    "water_temp_c":          "Temperatura (°C)",
    "ammonium":              "Amonio (µg/L)",
    "nitrate":               "Nitrato (µg/L)",
}


# ===========================================================================
# ParametroSensibilidad
# ===========================================================================

@dataclass
class ParametroSensibilidad:
    """
    Define un parámetro a perturbar en el análisis de sensibilidad.

    El muestreo es uniforme en [minimo, maximo] con LHS.
    Solo necesitás indicar el rango plausible del parámetro.

    Atributos comunes
    -----------------
    nombre          : Identificador único (columna en la tabla de resultados).
    categoria       : "reach" | "fuente" | "cabecera"
    campo           : Campo JSON a modificar.
                        reach    → "alpha_1", "beta_1", "alpha_2", "beta_2"
                        fuente   → "dbo5", "oxigeno_disuelto", "temperatura",
                                   "pH", "caudal"
                        cabecera → "caudal", "dbo5", "oxigeno_disuelto",
                                   "temperatura", "pH"
    minimo          : Límite inferior del rango uniforme.
    maximo          : Límite superior del rango uniforme.
    tipo            : "absoluto" → el valor muestreado REEMPLAZA al base.
                      "relativo" → el valor muestreado MULTIPLICA al base.
                                   (minimo=0.5, maximo=1.5 → ±50% del calibrado)

    Atributos por categoría
    -----------------------
    nombre_fuente   : (fuente)   nombre exacto del vertimiento en el JSON.
    tramos          : (reach)    índices de tramos a modificar — None = todos.
    nombre_estacion : (cabecera) nombre de la estación en wq_data — None = primera.
    """
    nombre:    str
    categoria: str
    campo:     str
    minimo:    float
    maximo:    float
    tipo:      str            = "absoluto"
    # Por categoría
    nombre_fuente:   Optional[str]       = None
    tramos:          Optional[List[int]] = None
    nombre_estacion: Optional[str]       = None

    def validar(self):
        """Lanza ValueError si la configuración es inconsistente."""
        if self.minimo >= self.maximo:
            raise ValueError(
                f"[{self.nombre}] minimo ({self.minimo}) debe ser menor que "
                f"maximo ({self.maximo})."
            )
        if self.categoria == "reach" and self.campo not in _CAMPOS_REACH:
            raise ValueError(
                f"[{self.nombre}] campo='{self.campo}' no válido para 'reach'. "
                f"Permitidos: {sorted(_CAMPOS_REACH)}"
            )
        if self.categoria == "fuente":
            if self.campo not in _CAMPOS_FUENTE:
                raise ValueError(
                    f"[{self.nombre}] campo='{self.campo}' no válido para 'fuente'. "
                    f"Permitidos: {sorted(_CAMPOS_FUENTE)}"
                )
            if self.nombre_fuente is None:
                raise ValueError(
                    f"[{self.nombre}] Se requiere 'nombre_fuente' para "
                    f"categoria='fuente'."
                )
        if self.categoria == "cabecera" and self.campo not in _CAMPOS_CABECERA:
            raise ValueError(
                f"[{self.nombre}] campo='{self.campo}' no válido para 'cabecera'. "
                f"Permitidos: {sorted(_CAMPOS_CABECERA)}"
            )
        if self.categoria not in {"reach", "fuente", "cabecera"}:
            raise ValueError(
                f"[{self.nombre}] categoria='{self.categoria}' no reconocida. "
                f"Usar 'reach', 'fuente' o 'cabecera'."
            )
        if self.tipo not in {"absoluto", "relativo"}:
            raise ValueError(
                f"[{self.nombre}] tipo='{self.tipo}' no reconocido. "
                f"Usar 'absoluto' o 'relativo'."
            )


# ===========================================================================
# LHS — muestreo
# ===========================================================================

def _muestrear_lhs(
    parametros: List[ParametroSensibilidad],
    n:          int,
    seed:       int,
) -> Dict[str, np.ndarray]:
    """
    Genera N muestras con Latin Hypercube Sampling para todos los parámetros.

    Retorna un dict {nombre_param: array de N valores escalados a [min, max]}.
    """
    d = len(parametros)
    sampler   = LatinHypercube(d=d, seed=seed)
    lhs_unit  = sampler.random(n=n)          # shape (n, d) — valores en [0, 1]

    muestras: Dict[str, np.ndarray] = {}
    for j, p in enumerate(parametros):
        # Escalar de [0, 1] a [minimo, maximo]
        muestras[p.nombre] = p.minimo + lhs_unit[:, j] * (p.maximo - p.minimo)

    return muestras


# ===========================================================================
# Modificadores del config JSON
# ===========================================================================

def _aplicar_valor(base: float, valor: float, tipo: str) -> float:
    if tipo == "relativo":
        return base * valor
    return valor   # absoluto


def _mod_reach(config: dict, param: ParametroSensibilidad, valor: float):
    reaches = config.get("reaches", [])
    if not reaches:
        raise ValueError("El JSON no tiene la sección 'reaches'.")
    indices = param.tramos if param.tramos is not None else list(range(len(reaches)))
    for i in indices:
        if i >= len(reaches):
            raise IndexError(
                f"[{param.nombre}] Índice de tramo {i} fuera de rango "
                f"(total={len(reaches)})."
            )
        base = float(reaches[i].get(param.campo, 1.0) or 1.0)
        reaches[i][param.campo] = _aplicar_valor(base, valor, param.tipo)


def _mod_fuente(config: dict, param: ParametroSensibilidad, valor: float):
    sources    = config.get("sources", [])
    encontrado = False
    for src in sources:
        if src.get("nombre") == param.nombre_fuente:
            base = float(src.get(param.campo, 0.0) or 0.0)
            src[param.campo] = _aplicar_valor(base, valor, param.tipo)
            encontrado = True
    if not encontrado:
        raise ValueError(
            f"[{param.nombre}] No se encontró la fuente '{param.nombre_fuente}' "
            f"en 'sources'."
        )


def _mod_cabecera(config: dict, param: ParametroSensibilidad, valor: float):
    wq_data = config.get("wq_data", [])
    if not wq_data:
        raise ValueError("El JSON no tiene la sección 'wq_data'.")
    if param.nombre_estacion:
        estacion = next(
            (s for s in wq_data if s.get("nombre_estacion") == param.nombre_estacion),
            None,
        )
        if estacion is None:
            raise ValueError(
                f"[{param.nombre}] Estación '{param.nombre_estacion}' "
                f"no encontrada en 'wq_data'."
            )
    else:
        estacion = wq_data[0]

    base   = float(estacion.get(param.campo, 0.0) or 0.0)
    nuevo  = _aplicar_valor(base, valor, param.tipo)
    estacion[param.campo] = nuevo

    if param.campo == "caudal":
        config.setdefault("simulacion", {})["q_cabecera"] = nuevo


def _modificar_config(config: dict, param: ParametroSensibilidad, valor: float):
    if param.categoria == "reach":
        _mod_reach(config, param, valor)
    elif param.categoria == "fuente":
        _mod_fuente(config, param, valor)
    elif param.categoria == "cabecera":
        _mod_cabecera(config, param, valor)


# ===========================================================================
# Worker  (nivel de módulo → serializable con pickle en Windows)
# ===========================================================================

def _worker_corrida(args: tuple):
    """
    Ejecuta una corrida de QUAL2K con la configuración pre-modificada.

    Recibe  : (run_id, config_dict, run_dir)
    Retorna : dict con run_id, exito y medias espaciales de variables de salida.
    """
    run_id, config_dict, run_dir = args

    import matplotlib
    matplotlib.use("Agg")
    import warnings
    warnings.filterwarnings("ignore")

    try:
        os.makedirs(run_dir, exist_ok=True)

        config_dict["header"]["filedir"] = run_dir

        json_path = os.path.join(run_dir, "config.json")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(config_dict, fh, indent=2, ensure_ascii=False)

        from scripts.run_from_json import run_simulacion

        data_exp = run_simulacion(
            json_path=json_path,
            generar_graficas=False,
            calcular_metricas=False,
            verbose=False,
        )

        if data_exp is None or data_exp.empty:
            return {"run_id": run_id, "exito": False, "medias": {}}

        cols   = [c for c in _VARIABLES_SALIDA if c in data_exp.columns]
        medias = {c: float(data_exp[c].mean()) for c in cols}
        return {"run_id": run_id, "exito": True, "medias": medias}

    except Exception as exc:
        return {"run_id": run_id, "exito": False, "medias": {}, "error": str(exc)}


def _limpiar_run(run_dir: str):
    """
    Limpia el directorio de una corrida tras extraer sus resultados.
    Conserva únicamente config.json (útil para debugging).
    Elimina todo lo demás: ejecutable, archivos FORTRAN y subdirectorios.
    """
    import shutil
    run_path = Path(run_dir)
    if not run_path.exists():
        return
    for entry in run_path.iterdir():
        try:
            if entry.is_dir():
                shutil.rmtree(entry)   # ej. resultados/
            elif entry.name != "config.json":
                entry.unlink()         # .q2k, .out, .DAT, .exe, etc.
        except Exception:
            pass


# ===========================================================================
# Función principal
# ===========================================================================

def analisis_sensibilidad(
    json_base:    str,
    parametros:   List[ParametroSensibilidad],
    n:            int  = 100,
    output_dir:   str  = "resultados/sensibilidad",
    seed:         int  = 42,
    n_workers:    int  = 4,
    limpiar_runs: bool = True,
) -> pd.DataFrame:
    """
    Ejecuta N corridas LHS de QUAL2K y calcula el SRCC de sensibilidad.

    Parámetros
    ----------
    json_base    : Ruta al JSON de simulación base.
    parametros   : Lista de ParametroSensibilidad (solo necesitan minimo/maximo).
    n            : Número de corridas (con LHS, 50–100 suele ser suficiente).
    output_dir   : Directorio de salida para resultados y gráficas.
    seed         : Semilla aleatoria para reproducibilidad.
    n_workers    : Número de procesos en paralelo.
    limpiar_runs : Si True, borra .q2k/.out/etc. tras cada corrida.

    Retorna
    -------
    DataFrame SRCC con índice = parámetros y columnas = variables de salida.
    """
    os.makedirs(output_dir, exist_ok=True)
    warnings.filterwarnings("ignore")

    # ── Validar ──────────────────────────────────────────────────────────
    print("Validando parámetros...")
    for p in parametros:
        p.validar()
    print(f"  OK — {len(parametros)} parámetros, {n} corridas LHS, "
          f"{n_workers} worker(s).\n")

    # ── Cargar JSON base ─────────────────────────────────────────────────
    with open(json_base, encoding="utf-8") as fh:
        config_base = json.load(fh)

    # ── LHS ──────────────────────────────────────────────────────────────
    muestras = _muestrear_lhs(parametros, n, seed)

    print("Rangos muestreados (LHS uniforme):")
    for p in parametros:
        v = muestras[p.nombre]
        print(f"  {p.nombre:<35}  [{p.minimo:.4g}, {p.maximo:.4g}]  "
              f"media_obs={v.mean():.4g}")
    print()

    _graficar_lhs(parametros, muestras, output_dir)

    # ── Preparar argumentos por corrida ──────────────────────────────────
    args_list = []
    for i in range(n):
        cfg = copy.deepcopy(config_base)
        for p in parametros:
            _modificar_config(cfg, p, float(muestras[p.nombre][i]))
        run_dir = os.path.join(output_dir, "runs", f"run_{i:03d}")
        args_list.append((i, cfg, run_dir))

    # ── Ejecución en paralelo ─────────────────────────────────────────────
    print(f"Lanzando {n} corridas con {n_workers} worker(s)...")
    print("=" * 70)

    resultados_raw = []
    pool = mp.Pool(processes=n_workers)
    try:
        futures = [pool.apply_async(_worker_corrida, (a,)) for a in args_list]
        for i, fut in enumerate(futures):
            try:
                res = fut.get(timeout=600)
                resultados_raw.append(res)
                estado  = "✓" if res["exito"] else "✗"
                detalle = f"  [{res.get('error', '')}]" if not res["exito"] else ""
                print(f"  {estado} Corrida {i:03d}{detalle}")
            except mp.TimeoutError:
                print(f"  ✗ Corrida {i:03d} — timeout")
                resultados_raw.append({"run_id": i, "exito": False, "medias": {}})
            finally:
                if limpiar_runs:
                    _limpiar_run(os.path.join(output_dir, "runs", f"run_{i:03d}"))
    finally:
        pool.close()
        pool.join()

    # ── Construir tabla de resultados ─────────────────────────────────────
    exitosas = sum(1 for r in resultados_raw if r["exito"])
    print(f"\nCorridas completadas: {exitosas}/{n}")

    filas = []
    for res in resultados_raw:
        if not res["exito"]:
            continue
        i    = res["run_id"]
        fila = {"run_id": i}
        for p in parametros:
            fila[p.nombre] = float(muestras[p.nombre][i])
        fila.update(res["medias"])
        filas.append(fila)

    if not filas:
        print("[Error] Ninguna corrida produjo resultados.")
        return pd.DataFrame()

    df = pd.DataFrame(filas)
    csv_path = os.path.join(output_dir, "resultados_por_corrida.csv")
    df.to_csv(csv_path, index=False)
    print(f"Resultados por corrida: {csv_path}\n")

    # ── SRCC ──────────────────────────────────────────────────────────────
    nombres = [p.nombre for p in parametros]
    df_srcc = _calcular_srcc(df, nombres, output_dir)

    return df_srcc


# ===========================================================================
# SRCC
# ===========================================================================

def _calcular_srcc(
    df:             pd.DataFrame,
    nombres_params: List[str],
    output_dir:     str,
) -> pd.DataFrame:
    """
    Calcula el SRCC entre cada parámetro y la media espacial de cada variable.

    |SRCC| ≈ 1  → el parámetro domina esa variable
    |SRCC| ≈ 0  → el parámetro no influye
    SRCC  > 0   → relación directa  (↑ parámetro → ↑ variable)
    SRCC  < 0   → relación inversa  (↑ parámetro → ↓ variable)
    """
    cols_sal = [c for c in _VARIABLES_SALIDA if c in df.columns]
    params   = [p for p in nombres_params    if p in df.columns]

    if not params or not cols_sal:
        print("[SRCC] No hay datos suficientes.")
        return pd.DataFrame()

    registros = []
    for param in params:
        fila = {"parametro": param}
        for col in cols_sal:
            datos = df[[param, col]].dropna()
            if len(datos) < 4:
                fila[col] = float("nan")
            else:
                rho, _ = spearmanr(datos[param], datos[col])
                fila[col] = round(rho, 4)
        registros.append(fila)

    df_srcc = pd.DataFrame(registros).set_index("parametro")

    csv_path = os.path.join(output_dir, "srcc_sensibilidad.csv")
    df_srcc.to_csv(csv_path)
    print(f"SRCC guardado: {csv_path}")

    etiquetas = {c: lbl for c, lbl in _VARIABLES_SALIDA.items() if c in cols_sal}
    _graficar_dispersiones(df, params, etiquetas, output_dir)
    _graficar_tornado(df_srcc, etiquetas, output_dir)
    _graficar_heatmap(df_srcc, etiquetas, output_dir)

    return df_srcc


# ===========================================================================
# Gráficas
# ===========================================================================

def _graficar_lhs(
    parametros: List[ParametroSensibilidad],
    muestras:   Dict[str, np.ndarray],
    output_dir: str,
):
    """
    Visualiza la cobertura del LHS:
      - Izquierda: histograma de cada parámetro (debe ser uniforme).
      - Derecha:   scatter matrix de los primeros 4 parámetros para verificar
                   que no hay correlación entre ellos (independencia).
    """
    n_params = len(parametros)
    if n_params == 0:
        return

    # ── Histogramas ───────────────────────────────────────────────────────
    ncols = min(3, n_params)
    nrows = (n_params + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 3 * nrows), squeeze=False)

    for k, p in enumerate(parametros):
        ax   = axes[k // ncols][k % ncols]
        vals = muestras[p.nombre]
        ax.hist(vals, bins=max(8, len(vals) // 5), color="steelblue",
                edgecolor="white", alpha=0.85, density=False)
        ax.axvline(vals.min(), color="gray",   lw=1, ls="--", label=f"min={p.minimo:.4g}")
        ax.axvline(vals.max(), color="gray",   lw=1, ls="--", label=f"max={p.maximo:.4g}")
        ax.axvline(vals.mean(), color="orange", lw=1.5, ls="-", label=f"μ={vals.mean():.4g}")
        ax.set_title(p.nombre, fontsize=9)
        ax.set_xlabel("Valor", fontsize=8)
        ax.set_ylabel("Frecuencia", fontsize=8)
        ax.legend(fontsize=6)

    for k in range(n_params, nrows * ncols):
        axes[k // ncols][k % ncols].set_visible(False)

    fig.suptitle("Cobertura LHS — distribución uniforme por parámetro", fontsize=11, y=1.01)
    fig.tight_layout()
    path = os.path.join(output_dir, "lhs_histogramas.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Histogramas LHS: {path}")

    # ── Scatter matrix (máximo 5 parámetros para legibilidad) ─────────────
    params_scatter = parametros[:5]
    m = len(params_scatter)
    if m >= 2:
        fig2, axes2 = plt.subplots(m, m, figsize=(2.5 * m, 2.5 * m))
        for r in range(m):
            for c in range(m):
                ax = axes2[r][c]
                xv = muestras[params_scatter[c].nombre]
                yv = muestras[params_scatter[r].nombre]
                if r == c:
                    ax.hist(xv, bins=10, color="steelblue", edgecolor="white", alpha=0.8)
                else:
                    ax.scatter(xv, yv, s=6, alpha=0.5, color="steelblue")
                if c == 0:
                    ax.set_ylabel(params_scatter[r].nombre, fontsize=6)
                if r == m - 1:
                    ax.set_xlabel(params_scatter[c].nombre, fontsize=6)
                ax.tick_params(labelsize=5)

        fig2.suptitle("Independencia entre parámetros (LHS)", fontsize=10, y=1.01)
        fig2.tight_layout()
        path2 = os.path.join(output_dir, "lhs_scatter_matrix.png")
        fig2.savefig(path2, dpi=150, bbox_inches="tight")
        plt.close(fig2)
        print(f"  Scatter matrix LHS: {path2}")


def _graficar_dispersiones(
    df:         pd.DataFrame,
    params:     List[str],
    etiquetas:  Dict[str, str],
    output_dir: str,
):
    """
    Scatter: valor del parámetro (eje X) vs media espacial de la variable
    simulada (eje Y). Una figura por parámetro, subplots por variable.
    """
    cols_sal = [c for c in etiquetas if c in df.columns]
    if not cols_sal:
        return
    ncols = min(3, len(cols_sal))
    nrows = (len(cols_sal) + ncols - 1) // ncols

    for param in params:
        if param not in df.columns:
            continue
        fig, axes = plt.subplots(nrows, ncols,
                                 figsize=(5 * ncols, 3.5 * nrows), squeeze=False)
        for j, col in enumerate(cols_sal):
            ax    = axes[j // ncols][j % ncols]
            datos = df[[param, col]].dropna()
            x, y  = datos[param].values, datos[col].values
            ax.scatter(x, y, alpha=0.5, s=20, color="steelblue")

            if len(x) >= 4:
                slope, intercept, *_ = linregress(x, y)
                x_line = np.linspace(x.min(), x.max(), 100)
                ax.plot(x_line, intercept + slope * x_line, "r--", lw=1.2)
                rho, _ = spearmanr(x, y)
                ax.annotate(
                    f"SRCC = {rho:+.3f}",
                    xy=(0.05, 0.92), xycoords="axes fraction",
                    fontsize=8, color="darkred",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7),
                )

            ax.set_xlabel(param, fontsize=8)
            ax.set_ylabel(etiquetas[col], fontsize=8)
            ax.set_title(etiquetas[col], fontsize=9)

        for j in range(len(cols_sal), nrows * ncols):
            axes[j // ncols][j % ncols].set_visible(False)

        fig.suptitle(f"Sensibilidad: {param}", fontsize=11, y=1.01)
        fig.tight_layout()
        fname = param.replace(" ", "_").replace("/", "-")
        path  = os.path.join(output_dir, f"scatter_{fname}.png")
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)

    print(f"  Scatter plots guardados en: {output_dir}")


def _graficar_tornado(
    df_srcc:    pd.DataFrame,
    etiquetas:  Dict[str, str],
    output_dir: str,
):
    """Tornado plot por variable. Barras ordenadas por |SRCC| descendente."""
    cols_sal = [c for c in etiquetas if c in df_srcc.columns]

    for col in cols_sal:
        serie = df_srcc[col].dropna().sort_values(key=abs)
        if serie.empty:
            continue
        fig, ax = plt.subplots(figsize=(7, max(3, 0.45 * len(serie))))
        colores = ["#d73027" if v < 0 else "#4575b4" for v in serie.values]
        ax.barh(serie.index, serie.values, color=colores, edgecolor="white", height=0.6)
        ax.axvline(0, color="black", lw=0.8)
        ax.set_xlabel("SRCC  (Spearman Rank Correlation Coefficient)", fontsize=9)
        ax.set_title(f"Tornado — {etiquetas[col]}", fontsize=10)
        ax.tick_params(axis="y", labelsize=8)
        ax.set_xlim(-1, 1)
        fig.tight_layout()
        fname = col.replace(" ", "_")
        path  = os.path.join(output_dir, f"tornado_{fname}.png")
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)

    print(f"  Tornado plots guardados en: {output_dir}")


def _graficar_heatmap(
    df_srcc:    pd.DataFrame,
    etiquetas:  Dict[str, str],
    output_dir: str,
):
    """Heatmap parámetros × variables con SRCC anotados."""
    cols_sal = [c for c in etiquetas if c in df_srcc.columns]
    if not cols_sal:
        return

    df_plot = df_srcc[cols_sal].copy()
    orden   = df_plot.abs().mean(axis=1).sort_values(ascending=False).index
    df_plot = df_plot.loc[orden]

    fig, ax = plt.subplots(
        figsize=(max(5, 1.5 * len(cols_sal)), max(3, 0.5 * len(df_plot)))
    )
    im = ax.imshow(df_plot.values, aspect="auto", cmap="RdBu_r", vmin=-1, vmax=1)
    plt.colorbar(im, ax=ax, label="SRCC")

    ax.set_xticks(range(len(cols_sal)))
    ax.set_xticklabels(
        [etiquetas[c] for c in cols_sal], rotation=30, ha="right", fontsize=8
    )
    ax.set_yticks(range(len(df_plot)))
    ax.set_yticklabels(df_plot.index, fontsize=8)
    ax.set_title(
        "Índices de sensibilidad (SRCC)\nazul = directa · rojo = inversa",
        fontsize=9,
    )

    for i in range(len(df_plot)):
        for j in range(len(cols_sal)):
            v = df_plot.iloc[i, j]
            if not np.isnan(v):
                color = "white" if abs(v) >= 0.6 else "black"
                ax.text(j, i, f"{v:.2f}", ha="center", va="center",
                        fontsize=7, color=color)

    fig.tight_layout()
    path = os.path.join(output_dir, "heatmap_srcc.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Heatmap guardado: {path}")
