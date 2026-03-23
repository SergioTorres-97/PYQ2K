"""
Bridge between Django and the qual2k package.
All heavy logic lives here; views stay thin.
"""
import os
import re
import sys
import io
import json
import shutil
import warnings
from pathlib import Path

import pandas as pd
from django.conf import settings

warnings.filterwarnings('ignore')

# Ensure PYQ2K root is in sys.path so qual2k and model packages are importable
# services.py → simulator → apps → webapp → PYQ2K  (index 3)
_PYQK_ROOT = Path(__file__).resolve().parents[3]
if str(_PYQK_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYQK_ROOT))


# ─── Directory helpers ───────────────────────────────────────────────────────

def prepare_work_dir(run) -> str:
    """
    Create media/runs/{pk}/, copy the FORTRAN exe, and place the Excel input.
    Returns the absolute path to the working directory.
    """
    work_dir_rel = os.path.join(settings.Q2K_RUNS_DIR, str(run.pk))
    work_dir_abs = os.path.join(str(settings.MEDIA_ROOT), work_dir_rel)
    os.makedirs(work_dir_abs, exist_ok=True)

    # Copy FORTRAN exe (must be in same folder as filedir)
    exe_src = str(settings.Q2K_EXE_MASTER)
    exe_dst = os.path.join(work_dir_abs, 'q2kfortran2_12.exe')
    if os.path.exists(exe_src) and not os.path.exists(exe_dst):
        shutil.copy2(exe_src, exe_dst)

    # Always write the Excel input fresh so edits are picked up on re-runs
    excel_dst = os.path.join(work_dir_abs, 'PlantillaBaseQ2K.xlsx')
    if run.uploaded_excel:
        shutil.copy2(run.uploaded_excel.path, excel_dst)
    else:
        _write_excel_from_json(run, excel_dst)

    # Persist work_dir on the model
    run.work_dir = work_dir_rel
    run.save(update_fields=['work_dir'])

    return work_dir_abs


def _write_excel_from_json(run, dst_path: str):
    """Reconstruct PlantillaBaseQ2K.xlsx from JSON fields stored on the run."""
    # JSONField already returns Python lists — no json.loads() needed
    reaches = pd.DataFrame(run.reaches_json or [])
    sources = pd.DataFrame(run.sources_json or [])
    wqdata = pd.DataFrame(run.wqdata_json or [])
    with pd.ExcelWriter(dst_path, engine='openpyxl') as writer:
        reaches.to_excel(writer, sheet_name='REACHES', index=False)
        sources.to_excel(writer, sheet_name='SOURCES', index=False)
        wqdata.to_excel(writer, sheet_name='WQ_DATA', index=False)


# ─── Model helpers ───────────────────────────────────────────────────────────

def build_header_dict(run, work_dir_abs: str) -> dict:
    return {
        'version': 'v2.12',
        'rivname': run.name,
        'filename': run.name,
        'filedir': work_dir_abs,
        'applabel': f"{run.name} ({run.xmon}/{run.xday}/{run.xyear})",
        'xmon': run.xmon,
        'xday': run.xday,
        'xyear': run.xyear,
        'timezonehour': run.timezonehour,
        'pco2': run.pco2,
        'dtuser': run.dtuser,
        'tf': run.tf,
        'IMeth': run.imeth,
        'IMethpH': run.imeth_ph,
    }


def build_reach_rates(run, n_reaches: int):
    """Returns reach_rates_custom dict or None (use defaults)."""
    if not run.reach_rates_json:
        return None
    from qual2k.core.config import Q2KConfig
    data = run.reach_rates_json  # already a dict (JSONField)

    def _list_or_none(key):
        val = data.get(key)
        if not val:
            return [None] * n_reaches
        return [v if v not in (None, '') else None for v in val]

    config = Q2KConfig({'version': 'v2.12', 'rivname': '', 'filename': '',
                        'filedir': '', 'applabel': '', 'xmon': 1, 'xday': 1,
                        'xyear': 2000, 'timezonehour': 0, 'pco2': 0.000347,
                        'dtuser': 0.00417, 'tf': 5, 'IMeth': 'Euler', 'IMethpH': 'Brent'})
    return config.generar_reach_rates_custom(
        n=n_reaches,
        kaaa_list=_list_or_none('kaaa'),
        khc_list=_list_or_none('khc'),
        kdcs_list=_list_or_none('kdcs'),
        kdc_list=_list_or_none('kdc'),
        khn_list=_list_or_none('khn'),
        kn_list=_list_or_none('kn'),
        ki_list=_list_or_none('ki'),
        khp_list=_list_or_none('khp'),
        kdt_list=_list_or_none('kdt'),
    )


# ─── Execution ───────────────────────────────────────────────────────────────

def execute_run(run_pk: int):
    """
    Full qual2k pipeline for one SimulationRun.
    Called from a background thread.
    """
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    from apps.simulator.models import SimulationRun
    from qual2k.core.model import Q2KModel

    run = SimulationRun.objects.get(pk=run_pk)
    try:
        run.status = 'running'
        run.error_message = ''
        run.save(update_fields=['status', 'error_message'])

        work_dir = prepare_work_dir(run)
        header = build_header_dict(run, work_dir)

        model = Q2KModel(work_dir, header)
        model.cargar_plantillas()

        # Apply user-defined global parameter overrides before configuring
        if run.config_rates_json:
            model.config.actualizar_rates(**run.config_rates_json)
        if run.config_light_json:
            model.config.actualizar_light(**run.config_light_json)

        n = len(model.data_reaches)
        reach_rates = build_reach_rates(run, n)

        model.configurar_modelo(
            numelem_default=run.numelem,
            q_cabecera=run.q_cabecera,
            reach_rates_custom=reach_rates,
        )
        model.generar_archivo_q2k()
        model.ejecutar_simulacion()
        model.analizar_resultados(
            generar_graficas=True,
            generar_comparacion=run.generar_comparacion,
        )

        kge_global = None
        kge_by_var = None
        if model._tiene_datos_observados():
            kge_by_var, kge_global = model.calcular_metricas_calibracion()
            # Sanitize: replace NaN/Inf (not JSON-serializable) with None
            import math
            kge_by_var = {
                k: (None if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else v)
                for k, v in kge_by_var.items()
            }
            if isinstance(kge_global, float) and (math.isnan(kge_global) or math.isinf(kge_global)):
                kge_global = None

        generate_plotly_run_charts(run)

        run.kge_global = kge_global
        run.kge_by_var_json = kge_by_var
        run.status = 'done'
        run.save(update_fields=['kge_global', 'kge_by_var_json', 'status'])

    except Exception as exc:
        from apps.simulator.models import SimulationRun as SR
        run = SR.objects.get(pk=run_pk)
        run.status = 'error'
        run.error_message = str(exc)
        run.save(update_fields=['status', 'error_message'])
        raise


def execute_pipeline(pipeline_pk: int):
    """
    Run all steps in a PipelineRun sequentially.
    Between steps, patches the next model's SOURCES Excel.
    """
    import sys
    sys.path.insert(0, str(settings.PYQK_ROOT if hasattr(settings, 'PYQK_ROOT') else
                          os.path.join(os.path.dirname(__file__), '..', '..', '..')))

    from apps.simulator.models import PipelineRun
    from model.pipeline_modelo_calidad import actualizar_vertimiento_desde_resultados

    pipeline = PipelineRun.objects.get(pk=pipeline_pk)
    try:
        pipeline.status = 'running'
        pipeline.save(update_fields=['status'])

        steps = list(pipeline.steps.select_related('run').order_by('order'))
        prev_csv_path = None

        for step in steps:
            run = step.run

            if prev_csv_path and step.nombre_vertimiento:
                # Ensure work dir exists and Excel is placed before patching
                work_dir = prepare_work_dir(run)
                excel_path = os.path.join(work_dir, 'PlantillaBaseQ2K.xlsx')
                actualizar_vertimiento_desde_resultados(
                    filepath_resultados=prev_csv_path,
                    filepath_excel_vertimientos=excel_path,
                    nombre_vertimiento=step.nombre_vertimiento,
                    fila_resultado=step.fila_resultado,
                )

            execute_run(run.pk)
            run.refresh_from_db()

            if run.status == 'error':
                raise RuntimeError(f'Paso {step.order} falló: {run.error_message}')

            prev_csv_path = run.results_csv_path

        pipeline.status = 'done'
        pipeline.save(update_fields=['status'])

    except Exception as exc:
        from apps.simulator.models import PipelineRun as PR
        pl = PR.objects.get(pk=pipeline_pk)
        pl.status = 'error'
        pl.error_message = str(exc)
        pl.save(update_fields=['status', 'error_message'])


# ─── Plotly chart generation ─────────────────────────────────────────────────

_COLORES_PLOTLY = [
    '#0077b6', '#2a9d8f', '#e9c46a', '#f4a261', '#e76f51',
    '#6c757d', '#264653', '#8ecae6', '#ffb703', '#adb5bd',
]

_CAL_OBS_PARES = [
    ('flow',                    'flow_obs'),
    ('water_temp_c',            'water_temp_c_obs'),
    ('total_suspended_solids',  'total_suspended_solids_obs'),
    ('dissolved_oxygen',        'dissolved_oxygen_obs'),
    ('carbonaceous_bod_fast',   'carbonaceous_bod_fast_obs'),
    ('total_kjeldahl_nitrogen', 'total_kjeldahl_nitrogen_obs'),
    ('ammonium',                'ammonium_obs'),
    ('total_phosphorus',        'total_phosphorus_obs'),
    ('conductivity',            'conductivity_obs'),
    ('nitrate',                 'nitrate_obs'),
    ('inorganic_phosphorus',    'inorganic_phosphorus_obs'),
    ('pathogen',                'pathogen_obs'),
    ('pH',                      'pH_obs'),
    ('alkalinity',              'alkalinity_obs'),
]

_PLOTLY_LAYOUT_BASE = dict(
    plot_bgcolor='white',
    paper_bgcolor='white',
    height=360,
    margin=dict(l=60, r=20, t=45, b=55),
    legend=dict(orientation='h', y=-0.18),
    xaxis=dict(showgrid=True, gridcolor='#e0e0e0', autorange='reversed'),
    yaxis=dict(showgrid=True, gridcolor='#e0e0e0'),
)


def _safe_name(col: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_]', '_', col)


def generate_plotly_run_charts(run) -> None:
    """
    Genera archivos JSON de Plotly para los resultados del run:
      - resultados/plotly/         → perfiles longitudinales
      - resultados/comparacion/plotly/ → simulado vs observado
    Se llama automáticamente al final de execute_run().
    """
    try:
        import plotly.graph_objects as go
        from qual2k.analysis.plotter import Q2KPlotter
    except ImportError:
        return

    csv_path = run.results_csv_path
    if not os.path.exists(csv_path):
        return

    plotter = Q2KPlotter()
    labels = plotter.labels_espanol
    x_col = 'Distancia Longitudinal (km)'

    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return

    if x_col not in df.columns:
        return

    df = df.sort_values(x_col)

    # Directorios de salida
    plotly_profiles_dir = os.path.join(run.graphs_dir, 'plotly')
    plotly_comp_dir = os.path.join(run.comparacion_dir, 'plotly')
    os.makedirs(plotly_profiles_dir, exist_ok=True)
    os.makedirs(plotly_comp_dir, exist_ok=True)

    # ── Perfiles longitudinales ───────────────────────────────────────────────
    sim_cols = [c for c in df.columns if c != x_col and not c.endswith('_obs')]
    for i, col in enumerate(sim_cols):
        color = _COLORES_PLOTLY[i % len(_COLORES_PLOTLY)]
        label = labels.get(col, col)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df[x_col], y=df[col],
            mode='lines', name='Simulado',
            line=dict(color=color, width=2.5),
        ))
        layout = dict(_PLOTLY_LAYOUT_BASE)
        layout['title'] = dict(text=label, font=dict(size=13, color='#222'))
        layout['xaxis_title'] = 'Distancia [km]'
        layout['yaxis_title'] = label
        fig.update_layout(**layout)
        with open(os.path.join(plotly_profiles_dir, f'{_safe_name(col)}.json'), 'w') as f:
            f.write(fig.to_json())

    # ── Simulado vs Observado ─────────────────────────────────────────────────
    for i, (sim_col, obs_col) in enumerate(_CAL_OBS_PARES):
        if obs_col not in df.columns or df[obs_col].dropna().empty:
            continue
        color = _COLORES_PLOTLY[i % len(_COLORES_PLOTLY)]
        label = labels.get(sim_col, sim_col)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df[x_col], y=df[sim_col],
            mode='lines', name='Simulado',
            line=dict(color=color, width=2.5),
        ))
        fig.add_trace(go.Scatter(
            x=df[x_col], y=df[obs_col],
            mode='markers', name='Observado',
            marker=dict(color='#111', size=8, symbol='circle'),
        ))
        layout = dict(_PLOTLY_LAYOUT_BASE)
        layout['title'] = dict(text=f'Calibración: {label}', font=dict(size=13, color='#222'))
        layout['xaxis_title'] = 'Distancia [km]'
        layout['yaxis_title'] = label
        fig.update_layout(**layout)
        with open(os.path.join(plotly_comp_dir, f'{_safe_name(sim_col)}.json'), 'w') as f:
            f.write(fig.to_json())


def collect_plotly_charts(run) -> dict:
    """
    Lee los JSON de Plotly guardados en disco.
    Retorna {profiles: [{title, json}, ...], comparacion: [{title, json}, ...]}.
    Falls back to vacío si no hay archivos (runs antiguos).
    """
    from qual2k.analysis.plotter import Q2KPlotter
    labels = Q2KPlotter().labels_espanol

    def read_dir(abs_dir):
        if not os.path.isdir(abs_dir):
            return []
        result = []
        for fname in sorted(os.listdir(abs_dir)):
            if not fname.endswith('.json'):
                continue
            var_name = fname[:-5]  # quita .json
            title = labels.get(var_name, var_name.replace('_', ' ').title())
            try:
                with open(os.path.join(abs_dir, fname), encoding='utf-8') as fh:
                    result.append({'title': title, 'json': fh.read()})
            except Exception:
                continue
        return result

    return {
        'profiles':    read_dir(os.path.join(run.graphs_dir, 'plotly')),
        'comparacion': read_dir(os.path.join(run.comparacion_dir, 'plotly')),
    }


# ─── Scenario comparison ─────────────────────────────────────────────────────

def generate_scenario_comparison(runs, variable: str, labels: dict = None,
                                  criterion_value: float = None,
                                  criterion_label: str = None):
    """
    Genera un gráfico interactivo Plotly comparando múltiples SimulationRuns.
    Retorna (fig_json: str | None, warnings: list[str]).
    """
    import plotly.graph_objects as go
    from qual2k.analysis.plotter import Q2KPlotter

    plotter = Q2KPlotter()
    labels_map = plotter.labels_espanol
    x_col = 'Distancia Longitudinal (km)'
    label_y = labels_map.get(variable, variable)

    fig = go.Figure()
    plotted = 0
    warn_msgs = []

    for i, run in enumerate(runs):
        csv_path = run.results_csv_path
        if not os.path.exists(csv_path):
            warn_msgs.append(
                f'"{run.name}": el archivo de resultados no se encontró en disco. '
                f'¿El run fue ejecutado correctamente?'
            )
            continue
        try:
            df = pd.read_csv(csv_path)
            if x_col not in df.columns:
                warn_msgs.append(f'"{run.name}": el CSV no contiene la columna de distancia.')
                continue
            if variable not in df.columns:
                warn_msgs.append(f'"{run.name}": la variable "{variable}" no existe en el CSV.')
                continue
            df = df.sort_values(x_col)
            color = _COLORES_PLOTLY[i % len(_COLORES_PLOTLY)]
            legend_label = (labels or {}).get(run.pk, run.name)
            fig.add_trace(go.Scatter(
                x=df[x_col], y=df[variable],
                mode='lines', name=legend_label,
                line=dict(color=color, width=2.5),
                hovertemplate='%{x:.2f} km → %{y:.3f}<extra>' + legend_label + '</extra>',
            ))
            plotted += 1
        except Exception as exc:
            warn_msgs.append(f'"{run.name}": error inesperado — {exc}')
            continue

    if plotted == 0:
        return None, warn_msgs

    # Criterio de calidad opcional
    if criterion_value is not None:
        crit_lbl = criterion_label.strip() if criterion_label and criterion_label.strip() \
                   else f'Criterio ({criterion_value})'
        fig.add_hline(
            y=criterion_value,
            line=dict(color='red', width=1.8, dash='dash'),
            annotation_text=crit_lbl,
            annotation_position='top right',
        )

    fig.update_layout(
        title=dict(text=f'Comparación de Escenarios: {label_y}', font=dict(size=15)),
        xaxis=dict(title='Distancia [km]', autorange='reversed',
                   showgrid=True, gridcolor='#e0e0e0'),
        yaxis=dict(title=label_y, showgrid=True, gridcolor='#e0e0e0'),
        plot_bgcolor='white',
        paper_bgcolor='white',
        showlegend=True,
        legend=dict(orientation='h', y=-0.22, x=0, xanchor='left'),
        height=480,
        margin=dict(l=65, r=25, t=55, b=90),
        hovermode='x unified',
    )

    return fig.to_json(), warn_msgs


def build_scenario_csv(runs, variable: str, labels: dict = None) -> str | None:
    """
    Construye un CSV con columnas: distancia_km, <variable>, escenario.
    Retorna el string CSV, o None si no hay datos.
    """
    from qual2k.analysis.plotter import Q2KPlotter

    x_col = 'Distancia Longitudinal (km)'
    label_y = Q2KPlotter().labels_espanol.get(variable, variable)
    rows = []

    for run in runs:
        csv_path = run.results_csv_path
        if not os.path.exists(csv_path):
            continue
        try:
            df = pd.read_csv(csv_path)
            if x_col not in df.columns or variable not in df.columns:
                continue
            df = df.sort_values(x_col)
            scenario_name = (labels or {}).get(run.pk, run.name)
            for _, row in df[[x_col, variable]].iterrows():
                rows.append({
                    'distancia_km': row[x_col],
                    label_y: row[variable],
                    'escenario': scenario_name,
                })
        except Exception:
            continue

    if not rows:
        return None
    return pd.DataFrame(rows).to_csv(index=False)


# ─── Graph helpers ────────────────────────────────────────────────────────────

def collect_graphs(run) -> dict:
    """Returns {profiles: [url, ...], comparacion: [url, ...]} — PNGs (legacy)."""

    def urls_in(abs_dir):
        if not os.path.isdir(abs_dir):
            return []
        rel = os.path.relpath(abs_dir, str(settings.MEDIA_ROOT)).replace('\\', '/')
        return [
            f"{settings.MEDIA_URL}{rel}/{f}"
            for f in sorted(os.listdir(abs_dir))
            if f.lower().endswith('.png')
        ]

    return {
        'profiles': urls_in(run.graphs_dir),
        'comparacion': urls_in(run.comparacion_dir),
    }
