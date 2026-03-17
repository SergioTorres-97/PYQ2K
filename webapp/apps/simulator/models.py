from django.db import models


class Project(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class SimulationRun(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('running', 'Ejecutando'),
        ('done', 'Completado'),
        ('error', 'Error'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='runs')
    name = models.CharField(max_length=200, help_text='Nombre del río (sin espacios)')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)

    # Input: Excel OR JSON manual
    uploaded_excel = models.FileField(upload_to='uploads/', null=True, blank=True)
    reaches_json = models.JSONField(null=True, blank=True)
    sources_json = models.JSONField(null=True, blank=True)
    wqdata_json = models.JSONField(null=True, blank=True)
    n_reaches = models.IntegerField(default=1)

    # Header parameters
    xmon = models.IntegerField(default=6)
    xday = models.IntegerField(default=27)
    xyear = models.IntegerField(default=2012)
    timezonehour = models.IntegerField(default=-5)
    pco2 = models.FloatField(default=0.000347)
    dtuser = models.FloatField(default=4.16666666666667e-3)
    tf = models.FloatField(default=5.0)
    imeth = models.CharField(max_length=10, default='Euler')
    imeth_ph = models.CharField(max_length=10, default='Brent')
    q_cabecera = models.FloatField(default=1.065e-6)
    numelem = models.IntegerField(default=10)

    # Reach rates per reach as JSON: {"kaaa":[...], "kdc":[...], ...}
    reach_rates_json = models.JSONField(null=True, blank=True)

    # Global model parameters (rates_dict / light_dict overrides)
    # Only stores keys the user explicitly changed; None = use QUAL2K defaults
    config_rates_json = models.JSONField(null=True, blank=True)
    config_light_json = models.JSONField(null=True, blank=True)

    # Opciones de gráficas
    generar_comparacion = models.BooleanField(
        default=True,
        help_text='Genera gráficas Simulado vs Observado (requiere datos en WQ_DATA más allá de CABECERA)'
    )

    # Working directory relative to MEDIA_ROOT
    work_dir = models.CharField(max_length=500, blank=True)

    # Results
    kge_global = models.FloatField(null=True, blank=True)
    kge_by_var_json = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.project.name} / {self.name}'

    @property
    def abs_work_dir(self):
        from django.conf import settings
        import os
        return os.path.join(str(settings.MEDIA_ROOT), self.work_dir)

    @property
    def results_csv_path(self):
        import os
        return os.path.join(self.abs_work_dir, 'resultados', f'{self.name}.csv')

    @property
    def graphs_dir(self):
        import os
        return os.path.join(self.abs_work_dir, 'resultados')

    @property
    def comparacion_dir(self):
        import os
        return os.path.join(self.abs_work_dir, 'resultados', 'comparacion')


class PipelineRun(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('running', 'Ejecutando'),
        ('done', 'Completado'),
        ('error', 'Error'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='pipelines')
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.project.name} / Pipeline: {self.name}'


class PipelineStep(models.Model):
    pipeline = models.ForeignKey(PipelineRun, on_delete=models.CASCADE, related_name='steps')
    order = models.PositiveIntegerField()
    run = models.OneToOneField(SimulationRun, on_delete=models.CASCADE)
    nombre_vertimiento = models.CharField(max_length=200, blank=True)
    fila_resultado = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'Paso {self.order} de {self.pipeline}'
