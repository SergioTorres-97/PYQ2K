from pathlib import Path
import multiprocessing as mp
from qual2k.core.calibrator_general import CalibracionPipeline

# ============================================================================
# CONFIGURACIÓN DE PATHS
# ============================================================================
base = Path(__file__).parent.parent

# ============================================================================
# CONFIGURACIONES DE LOS MODELOS
# ============================================================================

config_vargas = {
    'filepath': f'{base}/data/templates/Canal_vargas/Comprobacion',
    'header_dict': {
        "version": "v2.12",
        "rivname": "Canal_vargas",
        "filename": "Canal_vargas",
        "filedir": f'{base}/data/templates/Canal_vargas/Comprobacion',
        "applabel": "Canal_vargas (6/27/2012)",
        "xmon": 6,
        "xday": 27,
        "xyear": 2012,
        "timezonehour": -6,
        "pco2": 0.000347,
        "dtuser": 4.16666666666667E-03,
        "tf": 5,
        "IMeth": "Euler",
        "IMethpH": "Brent"
    },
    'q_cabecera': 2.3148E-06
}

config_tramo3s = {
    'filepath': f'{base}/data/templates/Tramo_3s/Comprobacion',
    'header_dict': {
        "version": "v2.12",
        "rivname": "Tramo_3s",
        "filename": "Tramo_3s",
        "filedir": f'{base}/data/templates/Tramo_3s/Comprobacion',
        "applabel": "Tramo_3s (6/27/2012)",
        "xmon": 6,
        "xday": 27,
        "xyear": 2012,
        "timezonehour": -6,
        "pco2": 0.000347,
        "dtuser": 4.16666666666667E-03,
        "tf": 5,
        "IMeth": "Euler",
        "IMethpH": "Brent"
    },
    'q_cabecera': 1.053E-06
}

config_chicamocha = {
    'filepath': f'{base}/data/templates/Chicamocha/Comprobacion',
    'header_dict': {
        "version": "v2.12",
        "rivname": "Chicamocha",
        "filename": "Chicamocha",
        "filedir": f'{base}/data/templates/Chicamocha/Comprobacion',
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
    },
    'q_cabecera': 1.053E-06
}

# ============================================================================
# PARÁMETROS A CALIBRAR
# ============================================================================

parametros_vargas = {
    'kaaa': (0.5, 4.5, False),  # (min, max, es_global)
    'kdc': (0.01, 2.0, False),
    'kn': (0.0001, 0.05, False),
    'khp': (0.1, 2.0, False),
    'kdt': (0.01, 2.0, False),
}

parametros_tramo3s = {
    'kaaa': (0.5, 4.5, False),
    'kdc': (0.01, 2.0, False),
    'kn': (0.0001, 0.05, False),
    'khp': (0.1, 2.0, False),
    'kdt': (0.01, 2.0, False),
}

parametros_chicamocha = {
    'kaaa': (0.5, 4.5, False),
    'kdc': (0.01, 2.0, False),
    'kn': (0.0001, 0.05, False),
    'khp': (0.1, 2.0, False),
    'kdt': (0.01, 2.0, False),
}

# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    """Función principal para ejecutar la calibración."""

    print("""
    ╔════════════════════════════════════════════════════════════════════════════╗
    ║                                                                            ║
    ║        CALIBRACIÓN AUTOMÁTICA DE QUAL2K - PIPELINE DE 3 MODELOS            ║
    ║                                                                            ║
    ╚════════════════════════════════════════════════════════════════════════════╝
    """)

    # ========================================================================
    # CREAR PIPELINE DE CALIBRACIÓN
    # ========================================================================

    calibrador = CalibracionPipeline(
        # Configuraciones de modelos
        config_vargas=config_vargas,
        config_tramo3s=config_tramo3s,
        config_chicamocha=config_chicamocha,

        # Parámetros a calibrar
        parametros_vargas=parametros_vargas,
        parametros_tramo3s=parametros_tramo3s,
        parametros_chicamocha=parametros_chicamocha,

        # ===== PARÁMETROS BÁSICOS DEL GA =====
        num_generations=50,  # Número de generaciones
        population_size=30,  # Tamaño de población
        num_parents_mating=15,  # Padres para apareamiento

        # ===== SELECCIÓN DE PADRES =====
        parent_selection_type="tournament",  # Tipo de selección
        k_tournament=3,  # Tamaño del torneo

        # ===== CRUCE (CROSSOVER) =====
        crossover_type="uniform",  # Tipo de cruce
        crossover_probability=0.80,  # Probabilidad de cruce

        # ===== MUTACIÓN =====
        mutation_type="adaptive",  # Tipo de mutación
        mutation_probability=[0.30, 0.10],  # Probabilidad adaptativa [inicial, final]
        mutation_percent_genes=20,  # Porcentaje de genes a mutar

        # ===== ELITISMO =====
        keep_elitism=3,  # Número de mejores soluciones a mantener

        # ===== CRITERIOS DE PARADA =====
        stop_criteria="saturate_15",  # Parar si no mejora en 15 generaciones

        # ===== OTROS PARÁMETROS =====
        random_seed=42,  # Semilla para reproducibilidad
        usar_paralelo=True,  # Usar procesamiento paralelo
        num_workers=4  # Número de workers paralelos
    )

    # ========================================================================
    # EJECUTAR CALIBRACIÓN
    # ========================================================================

    print("\n🚀 Iniciando calibración secuencial de los 3 modelos...\n")

    try:
        # Ejecutar (generar gráficas individuales automáticamente)
        resultado = calibrador.ejecutar(generar_graficas_individuales=True)

        # ====================================================================
        # GENERAR TODOS LOS OUTPUTS ADICIONALES
        # ====================================================================

        print("\n📊 Generando visualizaciones y reportes consolidados...")
        calibrador.exportar_todo()

        # ====================================================================
        # RESUMEN FINAL
        # ====================================================================

        print("\n" + "=" * 80)
        print("✅ CALIBRACIÓN COMPLETADA EXITOSAMENTE")
        print("=" * 80)

        print("\n📁 Ubicación de archivos:")
        print(f"  • Canal Vargas: {config_vargas['filepath']}")
        print(f"  • Tramo 3S: {config_tramo3s['filepath']}")
        print(f"  • Chicamocha: {config_chicamocha['filepath']}")
        print(f"  • Consolidados: {Path(config_vargas['filepath']).parent}")

        print("\n📈 Resultados finales:")
        if resultado.get('vargas'):
            print(f"  • Canal Vargas - KGE: {resultado['vargas'][1]:.6f}")
        if resultado.get('tramo3s'):
            print(f"  • Tramo 3S - KGE: {resultado['tramo3s'][1]:.6f}")
        if resultado.get('chicamocha'):
            print(f"  • Chicamocha - KGE: {resultado['chicamocha'][1]:.6f}")

        print("\n" + "=" * 80 + "\n")

    except KeyboardInterrupt:
        print("\n\n⚠️  Calibración interrumpida por el usuario")
        print("Los resultados parciales han sido guardados.\n")

    except Exception as e:
        print(f"\n\n❌ Error durante la calibración: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == '__main__':
    # Necesario para multiprocessing en Windows
    mp.freeze_support()

    # Ejecutar calibración
    main()