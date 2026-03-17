"""
Bridge between Django and the qual2k package.
All heavy logic lives here; views stay thin.
"""
import os
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


# ─── Scenario comparison ─────────────────────────────────────────────────────

def generate_scenario_comparison(runs, variable: str, labels: dict = None,
                                  criterion_value: float = None,
                                  criterion_label: str = None):
    """
    Generate a longitudinal-profile comparison plot for multiple SimulationRuns.
    Each run becomes one line. Returns a base64-encoded PNG string, or None on failure.

    Args:
        runs:             iterable of SimulationRun instances
        variable:         CSV column name to plot
        labels:           optional dict {run_pk: custom_label} for legend entries;
                          defaults to run.name when not provided
        criterion_value:  optional float — draws a horizontal dashed line at this value
        criterion_label:  optional str — legend label for the criterion line
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from qual2k.analysis.plotter import Q2KPlotter

    plotter = Q2KPlotter()
    colors = plotter.colores_elegantes
    x_col = 'Distancia Longitudinal (km)'

    fig, ax = plt.subplots(figsize=(10, 5))
    plotted = 0

    for i, run in enumerate(runs):
        csv_path = run.results_csv_path
        if not os.path.exists(csv_path):
            continue
        try:
            df = pd.read_csv(csv_path)
            if variable not in df.columns or x_col not in df.columns:
                continue
            df = df.sort_values(x_col)
            color = colors[i % len(colors)]
            legend_label = (labels or {}).get(run.pk, run.name)
            ax.plot(df[x_col], df[variable], color=color,
                    linewidth=2, label=legend_label)
            plotted += 1
        except Exception:
            continue

    if plotted == 0:
        plt.close()
        return None

    # Optional quality criterion — horizontal dashed line
    if criterion_value is not None:
        crit_lbl = criterion_label.strip() if criterion_label and criterion_label.strip() \
                   else f'Criterio ({criterion_value})'
        ax.axhline(y=criterion_value, color='red', linewidth=1.5,
                   linestyle='--', alpha=0.85, label=crit_lbl, zorder=5)

    label_y = plotter.get_label(variable)
    ax.set_title(f'Comparación de Escenarios: {label_y}',
                 fontweight='bold', fontstyle='italic', fontsize=12, pad=15)
    ax.set_xlabel('Distancia [km]', fontweight='bold', fontsize=10)
    ax.set_ylabel(label_y, fontsize=10, fontweight='bold')
    ax.invert_xaxis()
    ax.minorticks_on()
    ax.grid(which='major', linestyle='--', color='lightgray', linewidth=0.9, alpha=0.8)
    ax.grid(which='minor', linestyle=':', color='lightgray', linewidth=0.6, alpha=0.6)
    ax.tick_params(axis='both', which='major', length=6, width=1.2, direction='inout')
    ax.tick_params(axis='both', which='minor', length=3, width=0.8, direction='inout')
    ax.legend(loc='best', framealpha=0.9)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close()
    buf.seek(0)
    return 'data:image/png;base64,' + __import__('base64').b64encode(buf.read()).decode('utf-8')


# ─── Graph helpers ────────────────────────────────────────────────────────────

def collect_graphs(run) -> dict:
    """Returns {profiles: [url, ...], comparacion: [url, ...]}"""

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
