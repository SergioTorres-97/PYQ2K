from SALib.sample import saltelli
from SALib.analyze import sobol
import numpy as np
import matplotlib.pyplot as plt
from qual2k.core.model import Q2KModel
from pathlib import Path
import warnings

warnings.filterwarnings('ignore')

base = Path(__file__).parent.parent
filepath = f'{base}/data/templates/Chicamocha'

header_dict = {
    "version": "v2.12",
    "rivname": "Chicamocha",
    "filename": "Chicamocha",
    "filedir": filepath,
    "applabel": "Chicamocha (6/27/2012)",
    "xmon": 6,
    "xday": 27,
    "xyear": 2012,
    "timezonehour": -6,
    "pco2": 0.000347,
    "dtuser": 4.16666666666667E-03,
    "tf": 5,
    "IMeth": "Euler",
    "IMethpH": "Brent"
}

model = Q2KModel(filepath, header_dict)
model.cargar_plantillas(filepath + '\\PlantillaBaseQ2K.xlsx')
n = len(model.data_reaches)

problem = {
    'num_vars': 9,
    'names': ['kaaa', 'khc', 'kdcs', 'kdc', 'khn', 'kn', 'ki', 'khp', 'kdt'],
    'bounds': [
        [0.1, 2],  # kaaa
        [0.1, 3],  # khc
        [0.1, 0.5],  # kdcs
        [0.05, 5],  # kdc
        [0.05, 5],  # khn
        [1, 10],  # kn
        [0.1, 2],  # ki
        [0.05, 5],  # khp
        [0.05, 5]  # kdt
    ]
}

param_values = saltelli.sample(problem, 128)

print(f"Total simulaciones: {len(param_values)}")

Y = []
for idx, params in enumerate(param_values):
    if idx % 100 == 0:
        print(f"Simulación {idx}/{len(param_values)}")

    model = Q2KModel(filepath, header_dict)
    model.cargar_plantillas(filepath + '\\PlantillaBaseQ2K.xlsx')

    reach_rates_custom = model.config.generar_reach_rates_custom(
        n=n,
        kaaa_list=[params[0]] * n,
        khc_list=[params[1]] * n,
        kdcs_list=[params[2]] * n,
        kdc_list=[params[3]] * n,
        khn_list=[params[4]] * n,
        kn_list=[params[5]] * n,
        ki_list=[params[6]] * n,
        khp_list=[params[7]] * n,
        kdt_list=[params[8]] * n
    )

    model.configurar_modelo(reach_rates_custom=reach_rates_custom, q_cabecera=1.06007E-06)
    model.generar_archivo_q2k()
    model.ejecutar_simulacion()
    model.analizar_resultados(generar_graficas=False)
    resultados, kge_global = model.calcular_metricas_calibracion()

    Y.append(kge_global)

Y = np.array(Y)
Si = sobol.analyze(problem, Y)

print("\n" + "=" * 50)
print("RESULTADOS ANÁLISIS DE SENSIBILIDAD")
print("=" * 50)

print("\nS1 (Primer orden - efecto individual):")
for i, name in enumerate(problem['names']):
    print(f"  {name:8s}: {Si['S1'][i]:7.4f}")

print("\nST (Total - individual + interacciones):")
for i, name in enumerate(problem['names']):
    print(f"  {name:8s}: {Si['ST'][i]:7.4f}")

print("\nInteracciones (ST - S1):")
for i, name in enumerate(problem['names']):
    interaccion = Si['ST'][i] - Si['S1'][i]
    print(f"  {name:8s}: {interaccion:7.4f}")

indices_ordenados = np.argsort(Si['ST'])[::-1]
print("\n" + "=" * 50)
print("RANKING DE IMPORTANCIA (por ST):")
print("=" * 50)
for rank, i in enumerate(indices_ordenados, 1):
    print(f"{rank}. {problem['names'][i]:8s}: ST={Si['ST'][i]:.4f}")

parametros_importantes = [problem['names'][i] for i in indices_ordenados if Si['ST'][i] > 0.1]
parametros_medios = [problem['names'][i] for i in indices_ordenados if 0.01 <= Si['ST'][i] <= 0.1]
parametros_bajos = [problem['names'][i] for i in indices_ordenados if Si['ST'][i] < 0.01]

print("\n" + "=" * 50)
print("RECOMENDACIONES DE CALIBRACIÓN:")
print("=" * 50)
print(f"\nCALIBRAR (ST > 0.1): {parametros_importantes}")
print(f"CONSIDERAR (0.01 < ST < 0.1): {parametros_medios}")
print(f"FIJAR (ST < 0.01): {parametros_bajos}")

fig, axes = plt.subplots(2, 2, figsize=(14, 10))

axes[0, 0].bar(problem['names'], Si['S1'])
axes[0, 0].set_title('S1 - Primer Orden')
axes[0, 0].set_ylabel('Índice')
axes[0, 0].tick_params(axis='x', rotation=45)
axes[0, 0].grid(True, alpha=0.3)

axes[0, 1].bar(problem['names'], Si['ST'])
axes[0, 1].set_title('ST - Total')
axes[0, 1].set_ylabel('Índice')
axes[0, 1].tick_params(axis='x', rotation=45)
axes[0, 1].grid(True, alpha=0.3)

x = np.arange(len(problem['names']))
width = 0.35
axes[1, 0].bar(x - width / 2, Si['S1'], width, label='S1')
axes[1, 0].bar(x + width / 2, Si['ST'], width, label='ST')
axes[1, 0].set_xticks(x)
axes[1, 0].set_xticklabels(problem['names'], rotation=45)
axes[1, 0].set_ylabel('Índice')
axes[1, 0].set_title('Comparación S1 vs ST')
axes[1, 0].legend()
axes[1, 0].grid(True, alpha=0.3)

interacciones = Si['ST'] - Si['S1']
axes[1, 1].bar(problem['names'], interacciones)
axes[1, 1].set_title('Interacciones (ST - S1)')
axes[1, 1].set_ylabel('Índice')
axes[1, 1].tick_params(axis='x', rotation=45)
axes[1, 1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('analisis_sensibilidad.png', dpi=300)
plt.show()

print("\nGráfica guardada como 'analisis_sensibilidad.png'")