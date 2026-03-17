import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from qual2k.core.model import Q2KModel
import warnings
warnings.filterwarnings('ignore')

base = Path(__file__).parent.parent
filepath = str(base / 'data/templates/Canal_vargas/Comprobacion')
header_dict = {
    "version": "v2.12",    "rivname": "Canal_vargas",
    "filename": "Canal_vargas",
    "filedir": filepath,
    "applabel": "Canal_vargas (6/27/2012)",
    "xmon": 6, "xday": 27, "xyear": 2012,
    "timezonehour": -6,
    "pco2": 0.000347,
    "dtuser": 4.16666666666667E-03,
    "tf": 5,
    "IMeth": "Euler",
    "IMethpH": "Brent"
}

model = Q2KModel(filepath, header_dict)
model.cargar_plantillas()

n = len(model.data_reaches)
reach_rates_custom = model.config.generar_reach_rates_custom(
    n=n,
    kaaa_list=[1.824655, 3.984011, 3.757785, 1.816685],    # Tasa de aireación
    khc_list=[None] * n,                                    # Hidrólisis de carbono
    kdcs_list=[None] * n,                                   # Descomposición de carbono lento
    kdc_list=[1.307588, 0.181790, 0.075929, 0.313357],     # Descomposición de carbono rápido
    khn_list=[None] * n,                                    # Hidrólisis de nitrógeno
    kn_list=[0.004602, 0.001024, 0.001074, 0.004320],      # Nitrificación
    ki_list=[None] * n,                                     # Tasa de denitrificación
    khp_list=[0.836572, 1.234654, 0.649013, 0.630139],     # Hidrólisis de fósforo
    kdt_list=[0.767967, 1.485570, 1.442998, 0.807965]      # Detritos
)

model.configurar_modelo(reach_rates_custom=reach_rates_custom, q_cabecera=2.3148E-06)
model.generar_archivo_q2k()
model.ejecutar_simulacion()
model.analizar_resultados(generar_graficas=True)
_, kge_global = model.calcular_metricas_calibracion()

print(f'KGE: {kge_global}')
