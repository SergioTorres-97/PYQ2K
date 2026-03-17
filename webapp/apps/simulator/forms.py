from django import forms
from .models import Project, SimulationRun, PipelineRun

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class RunStep1Form(forms.Form):
    INPUT_CHOICES = [('upload', 'Subir Excel'), ('manual', 'Ingresar datos manualmente')]
    input_method = forms.ChoiceField(
        choices=INPUT_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial='upload',
    )
    uploaded_excel = forms.FileField(
        required=False,
        label='PlantillaBaseQ2K.xlsx',
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx'}),
        help_text='Archivo Excel con hojas REACHES, SOURCES y WQ_DATA',
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('input_method') == 'upload' and not cleaned.get('uploaded_excel'):
            self.add_error('uploaded_excel', 'Debes subir un archivo Excel.')
        return cleaned


class RunStep2Form(forms.ModelForm):
    class Meta:
        model = SimulationRun
        fields = [
            'name', 'xmon', 'xday', 'xyear', 'timezonehour',
            'pco2', 'dtuser', 'tf', 'imeth', 'imeth_ph',
            'q_cabecera', 'numelem', 'generar_comparacion',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'xmon': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12}),
            'xday': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 31}),
            'xyear': forms.NumberInput(attrs={'class': 'form-control'}),
            'timezonehour': forms.NumberInput(attrs={'class': 'form-control'}),
            'pco2': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'dtuser': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'tf': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'imeth': forms.Select(
                choices=[('Euler', 'Euler'), ('RK4', 'RK4')],
                attrs={'class': 'form-select'},
            ),
            'imeth_ph': forms.Select(
                choices=[('Brent', 'Brent'), ('Newton', 'Newton')],
                attrs={'class': 'form-select'},
            ),
            'q_cabecera': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0000001'}),
            'numelem': forms.NumberInput(attrs={'class': 'form-control', 'min': 5, 'max': 100}),
            'generar_comparacion': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Nombre del río',
            'xmon': 'Mes', 'xday': 'Día', 'xyear': 'Año',
            'timezonehour': 'Zona horaria (ej. -5)',
            'pco2': 'pCO₂ atmosférico (atm)',
            'dtuser': 'Paso de tiempo (días)',
            'tf': 'Duración simulación (días)',
            'imeth': 'Método de integración',
            'imeth_ph': 'Método pH',
            'q_cabecera': 'Caudal cabecera (m³/s)',
            'numelem': 'Elementos por tramo',
            'generar_comparacion': 'Gráficas Simulado vs Observado',
        }


class PipelineForm(forms.ModelForm):
    class Meta:
        model = PipelineRun
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }
