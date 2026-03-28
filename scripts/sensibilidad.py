"""
sensibilidad.py  –  Análisis de sensibilidad Monte Carlo / SRCC para QUAL2K
===========================================================================

Muestrea N combinaciones de parámetros, corre QUAL2K en paralelo y calcula
el SRCC (Spearman Rank Correlation Coefficient) entre cada parámetro y la
media espacial de cada variable simulada.

No requiere datos observados: trabaja únicamente con los perfiles simulados.

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
            nombre       = "alpha_1_global",
            categoria    = "reach",
            campo        = "alpha_1",
            distribucion = "normal",
            media        = 0.30,
            std          = 0.06,
            tipo         = "relativo",   # multiplica el valor base de cada tramo
        ),
        ParametroSensibilidad(
            nombre        = "dbo5_veolia",
            categoria     = "fuente",
            campo         = "dbo5",
            nombre_fuente = "VEOLIA",
            distribucion  = "lognormal",
            media         = 200.0,
            std           = 0.40,
            tipo          = "absoluto",  # reemplaza el valor base
        ),
        ParametroSensibilidad(
            nombre          = "caudal_cabecera",
            categoria       = "cabecera",
            campo           = "caudal",
            nombre_estacion = "CABECERA",
            distribucion    = "normal",
            media           = 1.5,
            std             = 0.30,
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
matplotlib.use("Agg")          # backend sin pantalla (obligatorio antes de importar pyplot)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, linregress

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

    Atributos comunes
    -----------------
    nombre        : Identificador único (columna en la tabla de resultados).
    categoria     : "reach" | "fuente" | "cabecera"
    campo         : Nombre del campo JSON a modificar.
    distribucion  : "normal" | "uniform" | "lognormal"
    media         : Valor central de la distribución.
                      · normal/uniform : media aritmética.
                      · lognormal      : mediana (= e^mu).
    std           : Desviación estándar.
                      · normal    : std aritmética.
                      · lognormal : sigma de ln(X) (dispersión relativa).
                      · uniform   : no se usa (definir minimo/maximo).
    minimo        : Límite inferior para muestreo y clip.
    maximo        : Límite superior para muestreo y clip.
    tipo          : "absoluto" → el valor muestreado REEMPLAZA al valor base.
                    "relativo" → el valor muestreado MULTIPLICA al valor base
                                 (media=1.0 ≡ sin cambio en la media).

    Atributos por categoría
    -----------------------
    nombre_fuente   : (fuente)   nombre del vertimiento en el JSON.
    tramos          : (reach)    índices de tramos a modificar — None = todos.
    nombre_estacion : (cabecera) nombre de la estación en wq_data — None = primera.
    """
    nombre:       str
    categoria:    str
    campo:        str
    distribucion: str
    media:        float
    std:          float           = 0.0
    minimo:       Optional[float] = None
    maximo:       Optional[float] = None
    tipo:         str             = "relativo"
    # Por categoría
    nombre_fuente:   Optional[str]       = None
    tramos:          Optional[List[int]] = None
    nombre_estacion: Optional[str]       = None

    def validar(self):
        """Lanza ValueError si la configuración es inconsistente."""
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
                    f"[{self.nombre}] Se requiere 'nombre_fuente' para categoria='fuente'."
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
        if self.distribucion not in {"normal", "uniform", "lognormal"}:
            raise ValueError(
                f"[{self.nombre}] distribucion='{self.distribucion}' no reconocida. "
                f"Usar 'normal', 'uniform' o 'lognormal'."
            )
        if self.tipo not in {"absoluto", "relativo"}:
            raise ValueError(
                f"[{self.nombre}] tipo='{self.tipo}' no reconocido. Usar 'absoluto' o 'relativo'."
            )


# ===========================================================================
# Muestreo
# ===========================================================================

def _muestrear(param: ParametroSensibilidad, rng: np.random.Generator) -> float:
    """Devuelve un valor aleatorio según la distribución del parámetro."""
    if param.distribucion == "normal":
        v = rng.normal(param.media, param.std)
    elif param.distribucion == "uniform":
        lo = param.minimo if param.minimo is not None else param.media - 3 * param.std
        hi = param.maximo if param.maximo is not None else param.media + 3 * param.std
        v = rng.uniform(lo, hi)
    elif param.distribucion == "lognormal":
        v = rng.lognormal(np.log(param.media), param.std)
    else:
        raise ValueError(f"Distribución no reconocida: {param.distribucion!r}")

    # Clip opcional
    if param.minimo is not None:
        v = max(v, param.minimo)
    if param.maximo is not None:
        v = min(v, param.maximo)
    return float(v)


# ===========================================================================
# Modificadores del config JSON
# ===========================================================================

def _aplicar_valor(base: float, valor: float, tipo: str) -> float:
    """Combina el valor base con el valor muestreado."""
    if tipo == "relativo":
        return base * valor
    return valor   # absoluto


def _mod_reach(config: dict, param: ParametroSensibilidad, valor: float):
    """
    Modifica un parámetro hidráulico (alpha_1, beta_1, alpha_2, beta_2)
    en los tramos indicados (o en todos si param.tramos es None).
    """
    reaches = config.get("reaches", [])
    if not reaches:
        raise ValueError("El JSON no tiene la sección 'reaches'.")

    indices = param.tramos if param.tramos is not None else list(range(len(reaches)))
    for i in indices:
        if i >= len(reaches):
            raise IndexError(
                f"[{param.nombre}] Índice de tramo {i} fuera de rango (total={len(reaches)})."
            )
        base = float(reaches[i].get(param.campo, 1.0) or 1.0)
        reaches[i][param.campo] = _aplicar_valor(base, valor, param.tipo)


def _mod_fuente(config: dict, param: ParametroSensibilidad, valor: float):
    """
    Modifica un campo de calidad (dbo5, oxigeno_disuelto, temperatura, pH, caudal)
    en el vertimiento identificado por param.nombre_fuente.
    """
    sources = config.get("sources", [])
    encontrado = False
    for src in sources:
        if src.get("nombre") == param.nombre_fuente:
            base = float(src.get(param.campo, 0.0) or 0.0)
            src[param.campo] = _aplicar_valor(base, valor, param.tipo)
            encontrado = True

    if not encontrado:
        raise ValueError(
            f"[{param.nombre}] No se encontró la fuente '{param.nombre_fuente}' "
            f"en la sección 'sources' del JSON."
        )


def _mod_cabecera(config: dict, param: ParametroSensibilidad, valor: float):
    """
    Modifica caudal o calidad de agua en la estación de cabecera de wq_data.
    Si param.nombre_estacion está definido, busca esa estación por nombre;
    de lo contrario usa la primera entrada de wq_data.
    Si el campo modificado es 'caudal', también actualiza simulacion.q_cabecera.
    """
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

    base = float(estacion.get(param.campo, 0.0) or 0.0)
    nuevo = _aplicar_valor(base, valor, param.tipo)
    estacion[param.campo] = nuevo

    # Mantener q_cabecera sincronizado si se modifica el caudal
    if param.campo == "caudal":
        config.setdefault("simulacion", {})["q_cabecera"] = nuevo


def _modificar_config(config: dict, param: ParametroSensibilidad, valor: float):
    """Despacha la modificación al modificador correcto según la categoría."""
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
    Ejecuta una corrida de QUAL2K con una configuración pre-modificada.

    Recibe  : (run_id, config_dict, run_dir)
    Retorna : dict con run_id, exito, medias espaciales de variables de salida.
    """
    run_id, config_dict, run_dir = args

    # Forzar backend sin pantalla en el proceso hijo
    import matplotlib
    matplotlib.use("Agg")
    import warnings
    warnings.filterwarnings("ignore")

    try:
        os.makedirs(run_dir, exist_ok=True)

        # Redirigir filedir al directorio de esta corrida
        config_dict["header"]["filedir"] = run_dir

        # Guardar el JSON modificado
        json_path = os.path.join(run_dir, "config.json")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(config_dict, fh, indent=2, ensure_ascii=False)

        # Importar aquí para no contaminar el namespace del proceso padre
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
    """Elimina archivos pesados de una corrida; conserva config.json."""
    extensiones   = {".q2k", ".out", ".err", ".log", ".DAT"}
    nombres_extra = {"q2kfortran2_12.exe"}
    for entry in Path(run_dir).iterdir():
        if entry.suffix in extensiones or entry.name in nombres_extra:
            try:
                entry.unlink()
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
    Ejecuta N corridas Monte Carlo de QUAL2K y calcula el SRCC de sensibilidad.

    Parámetros
    ----------
    json_base    : Ruta al JSON de simulación base (punto de partida).
    parametros   : Lista de ParametroSensibilidad a variar.
    n            : Número de corridas.
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
    print(f"  OK — {len(parametros)} parámetros, {n} corridas, {n_workers} worker(s).\n")

    # ── Cargar JSON base ──────────────────────────────────────────────────
    with open(json_base, encoding="utf-8") as fh:
        config_base = json.load(fh)

    # ── Muestreo ──────────────────────────────────────────────────────────
    rng = np.random.default_rng(seed)
    muestras: Dict[str, np.ndarray] = {
        p.nombre: np.array([_muestrear(p, rng) for _ in range(n)])
        for p in parametros
    }

    print("Distribuciones muestreadas:")
    for p in parametros:
        v = muestras[p.nombre]
        print(f"  {p.nombre:<35}  min={v.min():.4g}  media={v.mean():.4g}  max={v.max():.4g}")
    print()

    _graficar_distribuciones(parametros, muestras, output_dir)

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
                estado = "✓" if res["exito"] else "✗"
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
        i = res["run_id"]
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
    Calcula el SRCC entre cada parámetro y la media espacial de cada variable simulada.

    Interpretación:
      |SRCC| ≈ 1  → parámetro dominante para esa variable
      |SRCC| ≈ 0  → parámetro sin influencia
      SRCC  > 0   → relación directa  (↑ parámetro → ↑ variable)
      SRCC  < 0   → relación inversa  (↑ parámetro → ↓ variable)
    """
    cols_sal = [c for c in _VARIABLES_SALIDA if c in df.columns]
    params   = [p for p in nombres_params    if p in df.columns]

    if not params or not cols_sal:
        print("[SRCC] No hay datos suficientes para calcular índices.")
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

def _graficar_distribuciones(
    parametros: List[ParametroSensibilidad],
    muestras:   Dict[str, np.ndarray],
    output_dir: str,
):
    """Histograma de las distribuciones muestreadas para cada parámetro."""
    n = len(parametros)
    if n == 0:
        return
    ncols = min(3, n)
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 3.5 * nrows), squeeze=False)

    for k, p in enumerate(parametros):
        ax   = axes[k // ncols][k % ncols]
        vals = muestras[p.nombre]
        ax.hist(vals, bins=max(8, len(vals) // 5), color="steelblue",
                edgecolor="white", alpha=0.8, density=True)
        ax.axvline(vals.mean(), color="orange", lw=1.5, ls="--",
                   label=f"μ = {vals.mean():.4g}")
        ax.set_title(p.nombre, fontsize=9)
        ax.set_xlabel("Valor muestreado", fontsize=8)
        ax.legend(fontsize=7)

    # Ocultar subplots sobrantes
    for k in range(n, nrows * ncols):
        axes[k // ncols][k % ncols].set_visible(False)

    fig.suptitle("Distribuciones muestreadas (Monte Carlo)", fontsize=11, y=1.01)
    fig.tight_layout()
    path = os.path.join(output_dir, "distribuciones_parametros.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Gráfica distribuciones: {path}")


def _graficar_dispersiones(
    df:        pd.DataFrame,
    params:    List[str],
    etiquetas: Dict[str, str],
    output_dir: str,
):
    """
    Scatter plots: valor del parámetro (eje X) vs media espacial de la variable
    simulada (eje Y). Una figura por parámetro, subplots por variable de salida.
    Incluye recta de tendencia lineal y SRCC anotado.
    """
    cols_sal = [c for c in etiquetas if c in df.columns]
    if not cols_sal:
        return
    ncols = min(3, len(cols_sal))
    nrows = (len(cols_sal) + ncols - 1) // ncols

    for param in params:
        if param not in df.columns:
            continue
        fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 3.5 * nrows), squeeze=False)

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
    df_srcc:   pd.DataFrame,
    etiquetas: Dict[str, str],
    output_dir: str,
):
    """
    Tornado plot por variable de salida.
    Barras horizontales, parámetros ordenados de mayor a menor |SRCC|.
    Azul = relación directa, rojo = relación inversa.
    """
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
    df_srcc:   pd.DataFrame,
    etiquetas: Dict[str, str],
    output_dir: str,
):
    """Heatmap parámetros × variables de salida con valores SRCC anotados."""
    cols_sal = [c for c in etiquetas if c in df_srcc.columns]
    if not cols_sal:
        return

    # Ordenar parámetros por sensibilidad media descendente
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
        "Índices de sensibilidad (SRCC)\nazul = relación directa · rojo = relación inversa",
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
