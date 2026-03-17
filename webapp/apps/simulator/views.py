import io
import json
import os
import shutil
import zipfile

import pandas as pd
from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import PipelineForm, ProjectForm, RunStep1Form, RunStep2Form
from .models import PipelineRun, PipelineStep, Project, SimulationRun
from .services import collect_graphs, generate_scenario_comparison
from .tasks import launch_pipeline_async, launch_run_async


# ─── Parameter group definitions ─────────────────────────────────────────────

# Each entry: {'key': str, 'label': str, 'default': float}
# NOTE: complex types (consts, saturation_types, typeF, kai, kawindmethod) are
#       handled separately and are NOT exposed here as simple number inputs.
_RATES_GROUPS = [
    {
        'id': 'iss_stoich', 'label': 'Sólidos inorgánicos y Estequiometría',
        'params': [
            {'key': 'vss',  'label': 'Veloc. sediment. ISS — vss (m/d)',     'default': 0.1},
            {'key': 'mgC',  'label': 'Relación carbono — mgC (gC/gC)',        'default': 40},
            {'key': 'mgN',  'label': 'Relación nitrógeno — mgN (gN/gN)',      'default': 7.2},
            {'key': 'mgP',  'label': 'Relación fósforo — mgP (gP/gP)',        'default': 1},
            {'key': 'mgD',  'label': 'Relación peso seco — mgD (gD/gD)',      'default': 100},
            {'key': 'mgA',  'label': 'Relación clorofila — mgA (gA/gA)',      'default': 1},
        ],
    },
    {
        'id': 'reareacion', 'label': 'Reaireación y Estequiometría O₂',
        'params': [
            {'key': 'tka',  'label': 'θ reaireación — tka',                   'default': 1.024},
            {'key': 'roc',  'label': 'O₂ por oxidación C — roc (gO₂/gC)',    'default': 2.69},
            {'key': 'ron',  'label': 'O₂ por nitrificación — ron (gO₂/gN)',  'default': 4570.0},
            {'key': 'reaa', 'label': 'Coef. reaireación α — reaa',            'default': 3.93},
            {'key': 'reab', 'label': 'Coef. reaireación β — reab',            'default': 0.5},
            {'key': 'reac', 'label': 'Coef. reaireación γ — reac',            'default': 1.5},
        ],
    },
    {
        'id': 'inhibicion_o2', 'label': 'Inhibición / Mejora por O₂',
        'params': [
            {'key': 'Ksocf', 'label': 'Ks O₂ — oxidación DBO rápida (Ksocf)', 'default': 0.6},
            {'key': 'Ksona', 'label': 'Ks O₂ — nitrificación (Ksona)',         'default': 0.6},
            {'key': 'Ksodn', 'label': 'Ks O₂ — desnitrificación (Ksodn)',      'default': 0.6},
            {'key': 'Ksop',  'label': 'Ks O₂ — resp. fitoplancton (Ksop)',     'default': 0.6},
            {'key': 'Ksob',  'label': 'Ks O₂ — resp. alga bent. (Ksob)',       'default': 0.6},
        ],
    },
    {
        'id': 'dbo', 'label': 'DBO Carbonácea',
        'params': [
            {'key': 'kdc',   'label': 'Oxidación DBO rápida — kdc (/d)',        'default': 0.09},
            {'key': 'tkdc',  'label': 'θ DBO rápida — tkdc',                    'default': 1.047},
            {'key': 'khc',   'label': 'Hidrólisis DBO lenta — khc (/d)',         'default': 0.0},
            {'key': 'tkhc',  'label': 'θ hidrólisis DBO lenta — tkhc',          'default': 1.07},
            {'key': 'kdcs',  'label': 'Oxidación DBO lenta — kdcs (/d)',         'default': 0.0},
            {'key': 'tkdcs', 'label': 'θ oxidación DBO lenta — tkdcs',          'default': 1.047},
        ],
    },
    {
        'id': 'nitrogeno', 'label': 'Nitrógeno',
        'params': [
            {'key': 'khn',  'label': 'Hidrólisis N-org — khn (/d)',             'default': 0.015},
            {'key': 'tkhn', 'label': 'θ hidrólisis N-org — tkhn',               'default': 1.07},
            {'key': 'von',  'label': 'Sediment. N-org — von (m/d)',              'default': 0.0005},
            {'key': 'kn',   'label': 'Nitrificación — kn (/d)',                  'default': 0.08},
            {'key': 'tkn',  'label': 'θ nitrificación — tkn',                   'default': 1.07},
            {'key': 'ki',   'label': 'Desnitrificación — ki (/d)',               'default': 0.1},
            {'key': 'tki',  'label': 'θ desnitrificación — tki',                'default': 1.07},
            {'key': 'vdi',  'label': 'Coef. transf. desnitrif. sed. — vdi (m/d)', 'default': 0.8},
            {'key': 'tvdi', 'label': 'θ transf. desnitrif. — tvdi',             'default': 1.07},
        ],
    },
    {
        'id': 'fosforo', 'label': 'Fósforo',
        'params': [
            {'key': 'khp',  'label': 'Hidrólisis P-org — khp (/d)',             'default': 0.03},
            {'key': 'tkhp', 'label': 'θ hidrólisis P-org — tkhp',               'default': 1.07},
            {'key': 'vop',  'label': 'Sediment. P-org — vop (m/d)',              'default': 0.001},
            {'key': 'vip',  'label': 'Sediment. P-inorg — vip (m/d)',            'default': 0.8},
            {'key': 'kspi', 'label': 'Semi-sat. O₂ atenuac. P sed. — kspi',     'default': 1.0},
            {'key': 'Kdpi', 'label': 'Coef. sorción P-inorg — Kdpi (L/mgD)',    'default': 1000},
        ],
    },
    {
        'id': 'fitoplancton', 'label': 'Fitoplancton',
        'params': [
            {'key': 'kga',   'label': 'Crecimiento máx. — kga (/d)',            'default': 3.8},
            {'key': 'tkga',  'label': 'θ crecimiento — tkga',                   'default': 1.07},
            {'key': 'krea',  'label': 'Respiración — krea (/d)',                 'default': 0.15},
            {'key': 'tkrea', 'label': 'θ respiración — tkrea',                  'default': 1.07},
            {'key': 'kexa',  'label': 'Excreción — kexa (/d)',                   'default': 0.3},
            {'key': 'tkexa', 'label': 'θ excreción — tkexa',                    'default': 1.07},
            {'key': 'kdea',  'label': 'Mortalidad — kdea (/d)',                  'default': 0.1},
            {'key': 'tkdea', 'label': 'θ mortalidad — tkdea',                   'default': 1.07},
            {'key': 'ksn',   'label': 'Semi-sat. N — ksn (µg/L)',               'default': 100.0},
            {'key': 'ksp',   'label': 'Semi-sat. P — ksp (µg/L)',               'default': 10.0},
            {'key': 'ksc',   'label': 'Semi-sat. C inorg. — ksc (mol/L)',        'default': 0.000013},
            {'key': 'Isat',  'label': 'Cte. luz — Isat (langley/d)',             'default': 250.0},
            {'key': 'khnx',  'label': 'Preferencia amonio — khnx (µg/L)',       'default': 25.0},
            {'key': 'va',    'label': 'Velocidad sediment. — va (m/d)',          'default': 0.0},
        ],
    },
    {
        'id': 'fito_luxury', 'label': 'Fitoplancton — Consumo de Lujo (Droop)',
        'params': [
            {'key': 'NINpmin',   'label': 'Cuota interna N mín. — NINpmin (mgN/mgA)',   'default': 0.0},
            {'key': 'NIPpmin',   'label': 'Cuota interna P mín. — NIPpmin (mgP/mgA)',   'default': 0.0},
            {'key': 'NINpupmax', 'label': 'Captación N máx. — NINpupmax (mgN/mgA/d)',   'default': 0.0},
            {'key': 'NIPpupmax', 'label': 'Captación P máx. — NIPpupmax (mgP/mgA/d)',   'default': 0.0},
            {'key': 'KqNp',      'label': 'Semi-sat. interna N — KqNp (mgN/mgA)',        'default': 0.0},
            {'key': 'KqPp',      'label': 'Semi-sat. interna P — KqPp (mgP/mgA)',        'default': 0.0},
        ],
    },
    {
        'id': 'algas_bentonicas', 'label': 'Algas Bentónicas',
        'params': [
            {'key': 'kgaF',   'label': 'Crecimiento máx. — kgaF (mgA/m²/d)',    'default': 200.0},
            {'key': 'tkgaF',  'label': 'θ crecimiento — tkgaF',                  'default': 1.07},
            {'key': 'kreaF',  'label': 'Respiración — kreaF (/d)',                'default': 0.2},
            {'key': 'tkreaF', 'label': 'θ respiración — tkreaF',                 'default': 1.07},
            {'key': 'kexaF',  'label': 'Excreción — kexaF (/d)',                  'default': 0.12},
            {'key': 'tkexaF', 'label': 'θ excreción — tkexaF',                   'default': 1.07},
            {'key': 'kdeaF',  'label': 'Mortalidad — kdeaF (/d)',                 'default': 0.1},
            {'key': 'tkdeaF', 'label': 'θ mortalidad — tkdeaF',                  'default': 1.07},
            {'key': 'abmax',  'label': 'Cap. de carga — abmax (mgA/m²)',          'default': 1000.0},
            {'key': 'ksnF',   'label': 'Semi-sat. N — ksnF (µg/L)',               'default': 300.0},
            {'key': 'kspF',   'label': 'Semi-sat. P — kspF (µg/L)',               'default': 100.0},
            {'key': 'kscF',   'label': 'Semi-sat. C inorg. — kscF (mol/L)',        'default': 0.000013},
            {'key': 'Isatf',  'label': 'Cte. luz — Isatf (langley/d)',             'default': 100.0},
            {'key': 'khnxF',  'label': 'Preferencia amonio — khnxF (µg/L)',       'default': 25.0},
        ],
    },
    {
        'id': 'algas_luxury', 'label': 'Algas Bentónicas — Consumo de Lujo (Droop)',
        'params': [
            {'key': 'NINbmin',   'label': 'Cuota interna N mín. — NINbmin (mgN/mgA)',   'default': 0.72},
            {'key': 'NIPbmin',   'label': 'Cuota interna P mín. — NIPbmin (mgP/mgA)',   'default': 0.1},
            {'key': 'NINbupmax', 'label': 'Captación N máx. — NINbupmax (mgN/mgA/d)',   'default': 72.0},
            {'key': 'NIPbupmax', 'label': 'Captación P máx. — NIPbupmax (mgP/mgA/d)',   'default': 5.0},
            {'key': 'KqNb',      'label': 'Semi-sat. interna N — KqNb (mgN/mgA)',        'default': 0.9},
            {'key': 'KqPb',      'label': 'Semi-sat. interna P — KqPb (mgP/mgA)',        'default': 0.13},
        ],
    },
    {
        'id': 'detritos', 'label': 'Detritos (POM)',
        'params': [
            {'key': 'kdt',   'label': 'Tasa disolución — kdt (/d)',              'default': 0.23},
            {'key': 'tkdt',  'label': 'θ disolución — tkdt',                     'default': 1.07},
            {'key': 'ffast', 'label': 'Fracc. disol. → DBO rápida — ffast',      'default': 1.0},
            {'key': 'vdt',   'label': 'Veloc. sediment. — vdt (m/d)',             'default': 0.008},
        ],
    },
    {
        'id': 'patogenos', 'label': 'Patógenos',
        'params': [
            {'key': 'kpath',  'label': 'Tasa decaimiento — kpath (/d)',           'default': 0.8},
            {'key': 'tkpath', 'label': 'θ decaimiento — tkpath',                  'default': 1.07},
            {'key': 'vpath',  'label': 'Veloc. sediment. — vpath (m/d)',           'default': 1.0},
            {'key': 'aPath',  'label': 'Factor eficiencia luz — aPath',            'default': 1.0},
        ],
    },
]

_LIGHT_PARAMS = [
    # Extinción de luz
    {'key': 'PAR',          'label': 'Fracción PAR — PAR',                         'default': 0.47},
    {'key': 'kep',          'label': 'Extinción background — kep (/m)',              'default': 0.2},
    {'key': 'kela',         'label': 'Extinción lineal por clorofila — kela',        'default': 0.0088},
    {'key': 'kenla',        'label': 'Extinción no-lineal clorofila — kenla',        'default': 0.054},
    {'key': 'kess',         'label': 'Extinción por ISS — kess',                    'default': 0.052},
    {'key': 'kepom',        'label': 'Extinción por detritos POM — kepom',           'default': 0.174},
    # Modelo de radiación solar
    {'key': 'nfacBras',     'label': 'Coef. turbidez Bras — nfacBras (2=claro, 5=contaminado)', 'default': 2.0},
    {'key': 'atcRyanStolz', 'label': 'Transm. atmosférica Ryan-Stolzenbach — atcRyanStolz',     'default': 0.8},
    # Sedimento térmico
    {'key': 'Hsed',         'label': 'Espesor térmico sedimento — Hsed (cm)',        'default': 15.0},
    {'key': 'alphas',       'label': 'Difusividad térmica sed. — alphas (cm²/s)',    'default': 0.0064},
    {'key': 'rhos',         'label': 'Densidad sedimento — rhos (g/cm³)',             'default': 1.6},
    {'key': 'rhow',         'label': 'Densidad agua — rhow (g/cm³)',                  'default': 1.0},
    {'key': 'Cps',          'label': 'Calor específico sedimento — Cps (cal/g·°C)',   'default': 0.4},
    {'key': 'Cpw',          'label': 'Calor específico agua — Cpw (cal/g·°C)',        'default': 1.0},
]


def _save_config_rates(run, post_data):
    """Extract rate_glob_{key} from POST and store only explicitly-set values."""
    result = {}
    for group in _RATES_GROUPS:
        for param in group['params']:
            raw = post_data.get(f'rate_glob_{param["key"]}', '').strip()
            try:
                result[param['key']] = float(raw)
            except ValueError:
                pass
    run.config_rates_json = result if result else None
    run.save(update_fields=['config_rates_json'])


def _save_config_light(run, post_data):
    """Extract light_glob_{key} from POST and store only explicitly-set values."""
    result = {}
    for param in _LIGHT_PARAMS:
        raw = post_data.get(f'light_glob_{param["key"]}', '').strip()
        try:
            result[param['key']] = float(raw)
        except ValueError:
            pass
    run.config_light_json = result if result else None
    run.save(update_fields=['config_light_json'])


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _parse_excel_n_reaches(file_obj) -> int:
    df = pd.read_excel(file_obj, sheet_name='REACHES')
    return len(df)


def _save_reach_rates(run, post_data):
    """Extract kaaa_0..N, kdc_0..N, etc. from POST and store as JSON."""
    n = run.n_reaches
    params = ['kaaa', 'khc', 'kdcs', 'kdc', 'khn', 'kn', 'ki', 'khp', 'kdt']
    rates = {}
    has_any = False
    for p in params:
        values = []
        for i in range(n):
            raw = post_data.get(f'{p}_{i}', '').strip()
            try:
                values.append(float(raw))
                has_any = True
            except ValueError:
                values.append(None)
        rates[p] = values
    run.reach_rates_json = rates if has_any else None
    run.save(update_fields=['reach_rates_json'])


# ─── Projects ────────────────────────────────────────────────────────────────

def index(request):
    projects = Project.objects.prefetch_related('runs', 'pipelines').all()
    return render(request, 'simulator/index.html', {'projects': projects})


def project_new(request):
    form = ProjectForm(request.POST or None)
    if form.is_valid():
        project = form.save()
        return redirect('simulator:project_detail', pk=project.pk)
    return render(request, 'simulator/project_new.html', {'form': form})


def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    runs = project.runs.all()
    pipelines = project.pipelines.all()
    return render(request, 'simulator/project_detail.html', {
        'project': project, 'runs': runs, 'pipelines': pipelines,
    })


# ─── Runs ────────────────────────────────────────────────────────────────────

def run_new(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)

    if request.method == 'POST':
        form1 = RunStep1Form(request.POST, request.FILES)
        if form1.is_valid():
            method = form1.cleaned_data['input_method']

            run = SimulationRun.objects.create(
                project=project,
                name='provisional',
                status='pending',
            )

            if method == 'upload':
                excel_file = request.FILES['uploaded_excel']
                run.uploaded_excel = excel_file
                run.n_reaches = _parse_excel_n_reaches(excel_file)
                run.save(update_fields=['uploaded_excel', 'n_reaches'])
                return redirect('simulator:run_preview', pk=run.pk)
            else:
                reaches_data = json.loads(request.POST.get('reaches_json', '[]'))
                sources_data = json.loads(request.POST.get('sources_json', '[]'))
                wqdata_data  = json.loads(request.POST.get('wqdata_json',  '[]'))
                run.reaches_json = reaches_data
                run.sources_json = sources_data
                run.wqdata_json  = wqdata_data
                run.n_reaches    = len(reaches_data)
                run.save(update_fields=['reaches_json', 'sources_json', 'wqdata_json', 'n_reaches'])
                return redirect('simulator:run_configure', pk=run.pk)

    form1 = RunStep1Form()
    return render(request, 'simulator/run_new.html', {
        'project': project, 'form1': form1,
        'tables_reaches_json': '[]',
        'tables_sources_json': '[]',
        'tables_wqdata_json':  '[]',
    })


def _df_to_json_safe(df):
    """Convert DataFrame to JSON-safe list of dicts (NaN/NaT → None)."""
    return json.loads(df.where(pd.notna(df), other=None).to_json(orient='records'))


def run_preview(request, pk):
    """Step 1b: preview and edit input tables before model configuration."""
    run = get_object_or_404(SimulationRun, pk=pk)
    project = run.project

    if request.method == 'POST':
        try:
            reaches_data = json.loads(request.POST.get('reaches_json', '[]'))
            sources_data = json.loads(request.POST.get('sources_json', '[]'))
            wqdata_data  = json.loads(request.POST.get('wqdata_json', '[]'))
            run.reaches_json   = reaches_data
            run.sources_json   = sources_data
            run.wqdata_json    = wqdata_data
            run.n_reaches      = len(reaches_data)
            run.uploaded_excel = None  # data now lives in JSON fields
            run.save(update_fields=['reaches_json', 'sources_json', 'wqdata_json',
                                    'n_reaches', 'uploaded_excel'])
        except Exception as exc:
            messages.error(request, f'Error al procesar datos: {exc}')
        else:
            return redirect('simulator:run_configure', pk=run.pk)

    # ── Load data for preview ──────────────────────────────────────────────
    reaches_data, sources_data, wqdata_data = [], [], []
    load_error = None

    if run.uploaded_excel:
        try:
            path = run.uploaded_excel.path
            reaches_data = _df_to_json_safe(pd.read_excel(path, sheet_name='REACHES'))
            sources_data = _df_to_json_safe(pd.read_excel(path, sheet_name='SOURCES'))
            wqdata_data  = _df_to_json_safe(pd.read_excel(path, sheet_name='WQ_DATA'))
        except Exception as exc:
            load_error = str(exc)
    else:
        reaches_data = run.reaches_json or []
        sources_data = run.sources_json or []
        wqdata_data  = run.wqdata_json  or []

    return render(request, 'simulator/run_preview.html', {
        'run': run,
        'project': project,
        'reaches_json': json.dumps(reaches_data),
        'sources_json': json.dumps(sources_data),
        'wqdata_json':  json.dumps(wqdata_data),
        'load_error': load_error,
    })


def run_configure(request, pk):
    run = get_object_or_404(SimulationRun, pk=pk)
    project = run.project

    if request.method == 'POST':
        form2 = RunStep2Form(request.POST, instance=run)
        if form2.is_valid():
            # Use commit=False + explicit update_fields to avoid overwriting
            # reach_rates_json or other fields not in the form
            form2.save(commit=False)
            run.save(update_fields=[
                'name', 'xmon', 'xday', 'xyear', 'timezonehour',
                'pco2', 'dtuser', 'tf', 'imeth', 'imeth_ph',
                'q_cabecera', 'numelem', 'generar_comparacion',
            ])
            _save_reach_rates(run, request.POST)
            _save_config_rates(run, request.POST)
            _save_config_light(run, request.POST)
            messages.success(request, 'Configuración guardada.')
            return redirect('simulator:run_detail', pk=run.pk)
    else:
        form2 = RunStep2Form(instance=run)

    existing = run.reach_rates_json or {}
    return render(request, 'simulator/run_configure.html', {
        'run': run, 'project': project, 'form2': form2,
        'rate_params': ['kaaa', 'khc', 'kdcs', 'kdc', 'khn', 'kn', 'ki', 'khp', 'kdt'],
        'rate_labels': {
            'kaaa': 'Aireación (kaaa)',
            'khc': 'Hidrólisis CBODs (khc)',
            'kdcs': 'Oxidación CBODs (kdcs)',
            'kdc': 'Oxidación CBODf (kdc)',
            'khn': 'Hidrólisis N-org (khn)',
            'kn': 'Nitrificación (kn)',
            'ki': 'Desnitrificación (ki)',
            'khp': 'Hidrólisis P-org (khp)',
            'kdt': 'Detritos (kdt)',
        },
        'reach_range': range(run.n_reaches),
        'existing_rates': existing,
        # Global model parameters
        'rates_groups':     _RATES_GROUPS,
        'light_params':     _LIGHT_PARAMS,
        'config_rates':     run.config_rates_json or {},
        'config_light':     run.config_light_json or {},
    })


def run_edit_input(request, pk):
    """Allow editing the Step-1 input data (Excel or manual CSV) of an existing run."""
    run = get_object_or_404(SimulationRun, pk=pk)
    project = run.project

    def _json_to_csv(data):
        if not data:
            return ''
        return pd.DataFrame(data).to_csv(index=False)

    if request.method == 'POST':
        form1 = RunStep1Form(request.POST, request.FILES)
        if form1.is_valid():
            method = form1.cleaned_data['input_method']
            if method == 'upload':
                excel_file = request.FILES['uploaded_excel']
                run.uploaded_excel = excel_file
                run.n_reaches = _parse_excel_n_reaches(excel_file)
                run.reaches_json = None
                run.sources_json = None
                run.wqdata_json = None
                run.save(update_fields=['uploaded_excel', 'n_reaches',
                                        'reaches_json', 'sources_json', 'wqdata_json'])
            else:
                reaches_data = json.loads(request.POST.get('reaches_json', '[]'))
                sources_data = json.loads(request.POST.get('sources_json', '[]'))
                wqdata_data  = json.loads(request.POST.get('wqdata_json',  '[]'))
                run.reaches_json   = reaches_data
                run.sources_json   = sources_data
                run.wqdata_json    = wqdata_data
                run.n_reaches      = len(reaches_data)
                run.uploaded_excel = None
                run.save(update_fields=['reaches_json', 'sources_json', 'wqdata_json',
                                        'n_reaches', 'uploaded_excel'])
            # Reset status so the run is ready to re-execute
            run.status = 'pending'
            run.error_message = ''
            run.kge_global = None
            run.kge_by_var_json = None
            run.save(update_fields=['status', 'error_message', 'kge_global', 'kge_by_var_json'])
            if method == 'upload':
                return redirect('simulator:run_preview', pk=run.pk)
            return redirect('simulator:run_configure', pk=run.pk)

    has_excel = bool(run.uploaded_excel)
    initial_method = 'upload' if has_excel else 'manual'
    form1 = RunStep1Form()
    return render(request, 'simulator/run_edit_input.html', {
        'run': run,
        'project': project,
        'form1': form1,
        'initial_method': initial_method,
        'has_excel': has_excel,
        'existing_excel_name': run.uploaded_excel.name.split('/')[-1] if has_excel else '',
        'tables_reaches_json': json.dumps(run.reaches_json or []),
        'tables_sources_json': json.dumps(run.sources_json or []),
        'tables_wqdata_json':  json.dumps(run.wqdata_json  or []),
    })


_RATE_LABELS = {
    'kaaa': 'Aireación (kaaa)',
    'khc':  'Hidrólisis CBODs (khc)',
    'kdcs': 'Oxidación CBODs (kdcs)',
    'kdc':  'Oxidación CBODf (kdc)',
    'khn':  'Hidrólisis N-org (khn)',
    'kn':   'Nitrificación (kn)',
    'ki':   'Desnitrificación (ki)',
    'khp':  'Hidrólisis P-org (khp)',
    'kdt':  'Detritos (kdt)',
}

def run_detail(request, pk):
    run = get_object_or_404(SimulationRun, pk=pk)
    kge_data = run.kge_by_var_json or {}
    graphs = collect_graphs(run) if run.status == 'done' else {'profiles': [], 'comparacion': []}
    return render(request, 'simulator/run_detail.html', {
        'run': run, 'kge_data': kge_data, 'graphs': graphs,
        'existing_rates': run.reach_rates_json or {},
        'rate_params': list(_RATE_LABELS.keys()),
        'rate_labels': _RATE_LABELS,
        'reach_range': range(run.n_reaches),
        # Global overrides for display
        'rates_groups':  _RATES_GROUPS,
        'light_params':  _LIGHT_PARAMS,
        'config_rates':  run.config_rates_json or {},
        'config_light':  run.config_light_json or {},
    })


def run_status_api(request, pk):
    run = get_object_or_404(SimulationRun, pk=pk)
    return JsonResponse({
        'status': run.status,
        'kge_global': run.kge_global,
        'error': run.error_message,
    })


def run_sources_api(request, pk):
    """
    Returns the SOURCES (vertimientos) for a run, with the nearest row index
    in the results CSV pre-computed for each source (if results are available).
    Handles both manual-JSON runs and Excel-uploaded runs.
    """
    import numpy as np
    run = get_object_or_404(SimulationRun, pk=pk)
    sources_raw = run.sources_json or []

    # For Excel-uploaded runs sources_json is null — read directly from the file
    if not sources_raw:
        excel_path = None
        if run.uploaded_excel:
            try:
                excel_path = run.uploaded_excel.path
            except Exception:
                pass
        # Fall back to the copy in the work dir
        if not excel_path or not os.path.exists(excel_path):
            candidate = os.path.join(run.abs_work_dir, 'PlantillaBaseQ2K.xlsx')
            if os.path.exists(candidate):
                excel_path = candidate
        if excel_path:
            try:
                df_src = pd.read_excel(excel_path, sheet_name='SOURCES')
                sources_raw = df_src.to_dict(orient='records')
            except Exception:
                pass

    # Attempt to load result distances for automatic row-index lookup
    dist_array = None
    if run.status == 'done' and os.path.exists(run.results_csv_path):
        try:
            df_res = pd.read_csv(run.results_csv_path, usecols=['Distancia Longitudinal (km)'])
            dist_array = df_res['Distancia Longitudinal (km)'].values
        except Exception:
            pass

    data = []
    for s in sources_raw:
        nombre = s.get('NOMBRE_VERTIMIENTO', '')
        x = s.get('X_QUAL2K')
        fila = None
        if dist_array is not None and x is not None:
            try:
                fila = int(np.argmin(np.abs(dist_array - float(x))))
            except Exception:
                pass
        data.append({'nombre': nombre, 'x_qual2k': x, 'fila': fila})

    return JsonResponse({'sources': data})


@require_POST
def run_launch(request, pk):
    run = get_object_or_404(SimulationRun, pk=pk)
    if run.status == 'running':
        return JsonResponse({'error': 'Ya está ejecutando'}, status=400)
    run.status = 'pending'
    run.error_message = ''
    run.kge_global = None
    run.kge_by_var_json = None
    run.save(update_fields=['status', 'error_message', 'kge_global', 'kge_by_var_json'])
    launch_run_async(run.pk)
    return JsonResponse({'status': 'launched'})


def download_csv(request, pk):
    run = get_object_or_404(SimulationRun, pk=pk)
    path = run.results_csv_path
    if not os.path.exists(path):
        raise Http404('CSV no encontrado.')
    return FileResponse(open(path, 'rb'), as_attachment=True,
                        filename=f'{run.name}_resultados.csv')


def download_zip(request, pk):
    run = get_object_or_404(SimulationRun, pk=pk)
    work_dir = run.abs_work_dir
    if not os.path.isdir(work_dir):
        raise Http404('Directorio de resultados no encontrado.')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(work_dir):
            for fname in files:
                if fname == 'q2kfortran2_12.exe':
                    continue
                full = os.path.join(root, fname)
                arc = os.path.relpath(full, work_dir)
                zf.write(full, arc)
    buf.seek(0)
    return FileResponse(buf, as_attachment=True, filename=f'{run.name}_output.zip')


# ─── Copy ────────────────────────────────────────────────────────────────────

def _duplicate_run(original, name_suffix=' (copia)'):
    """
    Create a full copy of a SimulationRun ready to configure and re-run.
    References the same uploaded Excel file (safe: each execution copies it to
    its own work dir). JSON input data and all model parameters are duplicated.
    """
    new_run = SimulationRun.objects.create(
        project=original.project,
        name=original.name + name_suffix,
        status='pending',
        # Input data
        uploaded_excel=original.uploaded_excel.name if original.uploaded_excel else None,
        reaches_json=original.reaches_json,
        sources_json=original.sources_json,
        wqdata_json=original.wqdata_json,
        n_reaches=original.n_reaches,
        # Header parameters
        xmon=original.xmon,
        xday=original.xday,
        xyear=original.xyear,
        timezonehour=original.timezonehour,
        pco2=original.pco2,
        dtuser=original.dtuser,
        tf=original.tf,
        imeth=original.imeth,
        imeth_ph=original.imeth_ph,
        q_cabecera=original.q_cabecera,
        numelem=original.numelem,
        reach_rates_json=original.reach_rates_json,
        config_rates_json=original.config_rates_json,
        config_light_json=original.config_light_json,
    )
    return new_run


@require_POST
def run_copy(request, pk):
    original = get_object_or_404(SimulationRun, pk=pk)
    new_run = _duplicate_run(original)
    messages.success(request, f'Ejecución copiada como "{new_run.name}". Ajusta la configuración y ejecútala.')
    return redirect('simulator:run_configure', pk=new_run.pk)


@require_POST
def pipeline_copy(request, pk):
    original = get_object_or_404(PipelineRun, pk=pk)

    new_pipeline = PipelineRun.objects.create(
        project=original.project,
        name=original.name + ' (copia)',
        status='pending',
    )

    # PipelineStep.run is OneToOneField → must duplicate each run
    for step in original.steps.select_related('run').order_by('order'):
        new_run = _duplicate_run(step.run, name_suffix='')
        PipelineStep.objects.create(
            pipeline=new_pipeline,
            order=step.order,
            run=new_run,
            nombre_vertimiento=step.nombre_vertimiento,
            fila_resultado=step.fila_resultado,
        )

    messages.success(request, f'Pipeline copiado como "{new_pipeline.name}" con {original.steps.count()} pasos.')
    return redirect('simulator:pipeline_detail', pk=new_pipeline.pk)


# ─── Delete ──────────────────────────────────────────────────────────────────

@require_POST
def run_delete(request, pk):
    run = get_object_or_404(SimulationRun, pk=pk)
    project_pk = run.project_id
    work_dir = run.abs_work_dir
    run.delete()
    if os.path.isdir(work_dir):
        shutil.rmtree(work_dir, ignore_errors=True)
    return redirect('simulator:project_detail', pk=project_pk)


@require_POST
def pipeline_delete(request, pk):
    pipeline = get_object_or_404(PipelineRun, pk=pk)
    project_pk = pipeline.project_id
    pipeline.delete()
    return redirect('simulator:project_detail', pk=project_pk)


@require_POST
def project_delete(request, pk):
    project = get_object_or_404(Project, pk=pk)
    # Remove work dirs for every run before deleting the DB records
    for run in project.runs.all():
        work_dir = run.abs_work_dir
        if os.path.isdir(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)
    project.delete()  # cascades to SimulationRun and PipelineRun
    messages.success(request, f'Proyecto "{project.name}" eliminado correctamente.')
    return redirect('simulator:index')


# ─── Scenarios comparison ────────────────────────────────────────────────────

_SCENARIO_VARIABLES = [
    ('dissolved_oxygen', 'Oxígeno Disuelto (mg/L)'),
    ('water_temp_c', 'Temperatura del Agua (°C)'),
    ('flow', 'Caudal (m³/s)'),
    ('pH', 'pH (-)'),
    ('carbonaceous_bod_fast', 'DBO Carbonácea Rápida (mg/L)'),
    ('total_suspended_solids', 'Sólidos Suspendidos Totales (mg/L)'),
    ('ammonium', 'Amonio (ug/L)'),
    ('nitrate', 'Nitrato (ug/L)'),
    ('total_phosphorus', 'Fósforo Total (ug/L)'),
    ('total_kjeldahl_nitrogen', 'Nitrógeno Kjeldahl Total (ug/L)'),
    ('conductivity', 'Conductividad (μS/cm)'),
    ('inorganic_phosphorus', 'Fósforo Inorgánico (ug/L)'),
    ('pathogen', 'Patógenos (nmp/100mL)'),
    ('alkalinity', 'Alcalinidad (mg CaCO₃/L)'),
    ('carbonaceous_bod_slow', 'DBO Carbonácea Lenta (mg/L)'),
    ('nitrite', 'Nitrito (ug/L)'),
    ('total_nitrogen', 'Nitrógeno Total (ug/L)'),
    ('ammonia', 'Amoníaco (ug/L)'),
    ('inorganic_suspended_solids', 'Sólidos Suspendidos Inorgánicos (mg/L)'),
    ('ultimate_cbod', 'DBO Carbonácea Última (mg/L)'),
    ('detritus', 'Detritus (ug/L)'),
    ('const_i', 'Constituyente I (nmp/100mL)'),
    ('const_ii', 'Constituyente II (nmp/100mL)'),
    ('const_iii', 'Constituyente III (mg/L)'),
    ('flow_velocity', 'Velocidad de Flujo (m/s)'),
    ('hydraulic_head', 'Carga Hidráulica (m)'),
]


def project_scenarios(request, pk):
    project = get_object_or_404(Project, pk=pk)
    done_runs = project.runs.filter(status='done').order_by('name')

    # Pipelines with at least one done step — include step details for the template
    done_pipelines = (
        project.pipelines.filter(status='done')
        .prefetch_related('steps__run')
        .order_by('name')
    )
    pipeline_steps_ctx = []
    for pl in done_pipelines:
        steps = [
            {
                'order': s.order,
                'run_pk': s.run.pk,
                'run_name': s.run.name,
                'run_status': s.run.status,
                'run_kge': s.run.kge_global,
            }
            for s in pl.steps.select_related('run').order_by('order')
            if s.run.status == 'done'
        ]
        if steps:
            pipeline_steps_ctx.append({'pipeline': pl, 'steps': steps})

    chart_data_url = None
    selected_run_pks = []
    selected_pipeline_steps = {}   # {pipeline_pk: run_pk}
    selected_variable = 'dissolved_oxygen'
    criterion_value = None
    criterion_label = ''
    error = None

    if request.method == 'POST':
        selected_run_pks = [int(x) for x in request.POST.getlist('run_ids')]
        selected_variable = request.POST.get('variable', 'dissolved_oxygen')

        # Optional quality criterion line
        _cval = request.POST.get('criterion_value', '').strip()
        criterion_label = request.POST.get('criterion_label', '').strip()
        if _cval:
            try:
                criterion_value = float(_cval)
            except ValueError:
                error = 'El valor del criterio de calidad debe ser un número.'

        # Collect pipeline step selections
        selected_pipeline_ids = [int(x) for x in request.POST.getlist('pipeline_ids')]
        for pl_pk in selected_pipeline_ids:
            run_pk_str = request.POST.get(f'pipeline_step_{pl_pk}', '')
            if run_pk_str:
                selected_pipeline_steps[pl_pk] = int(run_pk_str)

        # Build combined run list + custom labels
        all_runs = list(SimulationRun.objects.filter(pk__in=selected_run_pks))
        labels = {}

        for pl_pk, step_run_pk in selected_pipeline_steps.items():
            try:
                pl = PipelineRun.objects.get(pk=pl_pk)
                step = pl.steps.select_related('run').get(run__pk=step_run_pk)
                run = step.run
                all_runs.append(run)
                labels[run.pk] = f'{pl.name} — Paso {step.order + 1} ({run.name})'
            except Exception:
                continue

        if not all_runs:
            error = 'Selecciona al menos un escenario o paso de pipeline.'
        elif not error:
            chart_data_url = generate_scenario_comparison(
                all_runs, selected_variable, labels=labels,
                criterion_value=criterion_value,
                criterion_label=criterion_label,
            )
            if chart_data_url is None:
                error = 'No se pudo generar la gráfica. Verifica que los escenarios tengan resultados.'

    return render(request, 'simulator/scenarios.html', {
        'project': project,
        'done_runs': done_runs,
        'pipeline_steps_ctx': pipeline_steps_ctx,
        'variables': _SCENARIO_VARIABLES,
        'chart_data_url': chart_data_url,
        'selected_run_pks': selected_run_pks,
        'selected_pipeline_steps': selected_pipeline_steps,
        'selected_variable': selected_variable,
        'criterion_value': criterion_value if criterion_value is not None else '',
        'criterion_label': criterion_label,
        'error': error,
    })


# ─── Pipelines ───────────────────────────────────────────────────────────────

def pipeline_new(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    available_runs = project.runs.all()

    if request.method == 'POST':
        form = PipelineForm(request.POST)
        if form.is_valid():
            pipeline = form.save(commit=False)
            pipeline.project = project
            pipeline.save()

            i = 0
            while f'run_{i}' in request.POST:
                run_pk_val = request.POST.get(f'run_{i}')
                nombre = request.POST.get(f'vertimiento_{i}', '')
                fila = int(request.POST.get(f'fila_{i}', 0) or 0)
                try:
                    sim_run = SimulationRun.objects.get(pk=run_pk_val, project=project)
                    PipelineStep.objects.create(
                        pipeline=pipeline, order=i,
                        run=sim_run, nombre_vertimiento=nombre, fila_resultado=fila,
                    )
                except SimulationRun.DoesNotExist:
                    pass
                i += 1

            return redirect('simulator:pipeline_detail', pk=pipeline.pk)

    form = PipelineForm()
    return render(request, 'simulator/pipeline_new.html', {
        'project': project, 'form': form, 'available_runs': available_runs,
    })


def pipeline_detail(request, pk):
    pipeline = get_object_or_404(PipelineRun, pk=pk)
    steps = pipeline.steps.select_related('run').order_by('order')
    return render(request, 'simulator/pipeline_detail.html', {
        'pipeline': pipeline, 'steps': steps,
    })


def pipeline_status_api(request, pk):
    pipeline = get_object_or_404(PipelineRun, pk=pk)
    steps_data = [
        {'order': s.order, 'name': s.run.name, 'status': s.run.status}
        for s in pipeline.steps.select_related('run').order_by('order')
    ]
    return JsonResponse({
        'status': pipeline.status,
        'steps': steps_data,
        'error': pipeline.error_message,
    })


@require_POST
def pipeline_launch(request, pk):
    pipeline = get_object_or_404(PipelineRun, pk=pk)
    if pipeline.status == 'running':
        return JsonResponse({'error': 'Pipeline ya está ejecutando'}, status=400)
    pipeline.status = 'pending'
    pipeline.error_message = ''
    pipeline.save(update_fields=['status', 'error_message'])
    launch_pipeline_async(pipeline.pk)
    return JsonResponse({'status': 'launched'})
