import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")
import re
import os

class Q2KPlotter:
    """
    Genera gráficas de resultados de QUAL2K.
    """

    def __init__(self):
        """Inicializa configuración de matplotlib"""
        plt.rcParams.update({
            "font.size": 12,
            "axes.titlesize": 16,
            "axes.labelsize": 13,
            "axes.edgecolor": "black",
            "axes.linewidth": 1.2,
            "grid.linestyle": "--",
            "grid.color": "lightgray",
            "grid.alpha": 0.7,
            "figure.figsize": (9, 5),
            "axes.facecolor": "white"
        })

        self.colores_elegantes = [
            '#0077b6', '#2a9d8f', '#e9c46a', '#f4a261', '#e76f51',
            '#6c757d', '#264653', '#8ecae6', '#ffb703', '#adb5bd'
        ]

        # Mapeo de labels en inglés a español con unidades
        self.labels_espanol = {
            'conductivity': 'Conductividad (μS/cm)',
            'inorganic_suspended_solids': 'Sólidos Suspendidos Inorgánicos (mg/L)',
            'dissolved_oxygen': 'Oxígeno Disuelto (mg/L)',
            'carbonaceous_bod_slow': 'DBO Carbonácea Lenta (mg/L)',
            'carbonaceous_bod_fast': 'DBO Carbonácea Rápida (mg/L)',
            'nitrite': 'Nitrito (ug/L)',
            'ammonium': 'Amonio (ug/L)',
            'nitrate': 'Nitrato (ug/L)',
            'organic_phosphorus': 'Fósforo Orgánico (ug/L)',
            'inorganic_phosphorus': 'Fósforo Inorgánico (ug/L)',
            'detritus': 'Detritus (ug/L)',
            'pathogen': 'Patógenos (nmp/100mL)',
            'alkalinity': 'Alcalinidad (mg CaCO₃/L)',
            'const_i': 'Constituyente I (nmp/100mL)',
            'const_ii': 'Constituyente II (nmp/100mL)',
            'const_iii': 'Constituyente III (mg/L)',
            'pH': 'pH (-)',
            'total_nitrogen': 'Nitrógeno Total (ug/L)',
            'total_phosphorus': 'Fósforo Total (ug/L)',
            'total_kjeldahl_nitrogen': 'Nitrógeno Kjeldahl Total (ug/L)',
            'total_suspended_solids': 'Sólidos Suspendidos Totales (mg/L)',
            'ultimate_cbod': 'DBO Carbonácea Última (mg/L)',
            'ammonia': 'Amoníaco (ug/L)',
            'water_temp_c': 'Temperatura del Agua (°C)',
            'flow': 'Caudal (m³/s)',
            'hydraulic_head': 'Carga Hidráulica (m)',
            'channel_top_width': 'Ancho Superior del Canal (m)',
            'cross_section_area': 'Área de Sección Transversal (m²)',
            'flow_velocity': 'Velocidad de Flujo (m/s)',
            'travel_time': 'Tiempo de Viaje (días)',
        }

    def _setup_axis(self, ax, df, x_col, label_y, titulo, xlabel, ylabel):
        """Aplica configuración común de ejes, grilla y ticks."""
        ax.set_title(
            titulo if titulo else f"Perfil Longitudinal de {label_y}",
            fontweight="bold", fontstyle="italic", fontsize=12, pad=15
        )
        ax.set_xlabel(xlabel, fontweight="bold", fontsize=10)
        ax.set_ylabel(ylabel if ylabel else label_y, fontsize=10, fontweight="bold")
        ax.invert_xaxis()
        ax.set_xlim(df[x_col].max(), 0)
        ax.minorticks_on()
        ax.grid(which='major', linestyle='--', color='lightgray', linewidth=0.9, alpha=0.8)
        ax.grid(which='minor', linestyle=':', color='lightgray', linewidth=0.6, alpha=0.6)
        ax.tick_params(axis='both', which='major', length=6, width=1.2, direction='inout')
        ax.tick_params(axis='both', which='minor', length=3, width=0.8, direction='inout')

    def get_label(self, col_name: str) -> str:
        return self.labels_espanol.get(col_name, col_name)

    def plot_parametro(self, df: pd.DataFrame, x_col: str, y_col: str,
                       rutaGuardado: str, titulo: str = "",
                       xlabel: str = "Distancia (km)", ylabel: str = None,
                       color: str = "#0077b6") -> None:
        """
        Genera gráfica de un parámetro individual.

        Args:
            df: DataFrame con datos
            x_col: Nombre de columna para eje X
            y_col: Nombre de columna para eje Y
            rutaGuardado: Ruta donde guardar la gráfica
            titulo: Título de la gráfica
            xlabel: Etiqueta del eje X
            ylabel: Etiqueta del eje Y
            color: Color de la línea
        """
        nombre_archivo = re.sub(r'[^A-Za-z0-9áéíóúÁÉÍÓÚñÑ]+', '_', y_col)
        nombre_archivo = re.sub(r'_+', '_', nombre_archivo).strip('_')

        fig, ax = plt.subplots()
        ax.plot(df[x_col], df[y_col], color=color, markersize=6, linewidth=2)
        self._setup_axis(ax, df, x_col, self.get_label(y_col), titulo, xlabel, ylabel)
        plt.tight_layout()
        plt.savefig(os.path.join(rutaGuardado, f'{nombre_archivo}.png'), bbox_inches='tight', dpi=300)
        plt.close()

    def plot_all_params(self, wq: pd.DataFrame, rutaGuardado: str) -> None:
        """
        Genera gráficas de todos los parámetros modelados.

        Args:
            wq: DataFrame con datos de calidad de agua
            rutaGuardado: Ruta donde guardar las gráficas
        """
        columnas_graficas = list(wq.columns)
        columnas_graficas.remove('Distancia Longitudinal (km)')
        x = 'Distancia Longitudinal (km)'

        for i in range(len(columnas_graficas)):
            color = self.colores_elegantes[i % len(self.colores_elegantes)]
            self.plot_parametro(
                wq,
                x_col=x,
                y_col=columnas_graficas[i],
                rutaGuardado=rutaGuardado,
                titulo='',
                xlabel='Distancia [km]',
                ylabel=None,
                color=color
            )

    def plot_parametro_cal_obs(self, df: pd.DataFrame, x_col: str,
                               sim_col: str, obs_col: str,
                               rutaGuardado: str, titulo: str = "",
                               xlabel: str = "Distancia (km)",
                               ylabel: str = None,
                               color: str = "#0077b6",
                               color_obs: str = "black") -> None:
        """
        Genera gráfica comparativa de parámetro modelado vs observado.

        Args:
            df: DataFrame con datos
            x_col: Nombre de columna para eje X
            sim_col: Nombre de columna simulada
            obs_col: Nombre de columna observada
            rutaGuardado: Ruta donde guardar la gráfica
            titulo: Título de la gráfica
            xlabel: Etiqueta del eje X
            ylabel: Etiqueta del eje Y
            color: Color de la línea simulada
            color_obs: Color de los puntos observados
        """
        nombre_archivo = re.sub(r'[^A-Za-z0-9áéíóúÁÉÍÓÚñÑ]+', '_', sim_col)
        nombre_archivo = re.sub(r'_+', '_', nombre_archivo).strip('_')

        label_sim = self.get_label(sim_col)
        fig, ax = plt.subplots()
        ax.plot(df[x_col], df[sim_col], color=color, linewidth=2, label="Simulado")
        ax.scatter(df[x_col], df[obs_col], color=color_obs, s=40, label="Observado")
        titulo_cal = titulo if titulo else f"Calibración: {label_sim}"
        self._setup_axis(ax, df, x_col, label_sim, titulo_cal, xlabel, ylabel)
        ax.legend(loc='best', framealpha=0.9)
        plt.tight_layout()
        plt.savefig(os.path.join(rutaGuardado, f'{nombre_archivo}.png'), bbox_inches='tight', dpi=300)
        plt.close()

    def plot_all_params_cal_obs(self, df: pd.DataFrame, rutaGuardado: str) -> None:
        """
        Genera todas las gráficas comparativas modelado vs observado.

        Args:
            df: DataFrame con datos modelados y observados
            rutaGuardado: Ruta donde guardar las gráficas
        """
        x = 'Distancia Longitudinal (km)'

        pares = [
            ("flow","flow_obs"),
            ("water_temp_c", "water_temp_c_obs"),
            ("total_suspended_solids", "total_suspended_solids_obs"),
            ("dissolved_oxygen", "dissolved_oxygen_obs"),
            ("carbonaceous_bod_fast", "carbonaceous_bod_fast_obs"),
            ("total_kjeldahl_nitrogen", "total_kjeldahl_nitrogen_obs"),
            ("ammonium", "ammonium_obs"),
            ("total_phosphorus", "total_phosphorus_obs"),
            ("conductivity",'conductivity_obs'),
            ("nitrate", "nitrate_obs"),
            ("inorganic_phosphorus","inorganic_phosphorus_obs"),
            ("pathogen", "pathogen_obs"),
            ("pH", "pH_obs"),
            ("alkalinity", "alkalinity_obs"),
        ]

        for i, (sim_col, obs_col) in enumerate(pares):
            # Omitir si la columna observada no existe o no tiene datos válidos
            if obs_col not in df.columns or df[obs_col].dropna().empty:
                continue
            color = self.colores_elegantes[i % len(self.colores_elegantes)]
            self.plot_parametro_cal_obs(
                df,
                x_col=x,
                sim_col=sim_col,
                obs_col=obs_col,
                rutaGuardado=rutaGuardado,
                titulo='',
                xlabel="Distancia [km]",
                ylabel=None,
                color=color,
                color_obs="black"
            )