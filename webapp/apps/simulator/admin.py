from django.contrib import admin
from .models import Project, SimulationRun, PipelineRun, PipelineStep

admin.site.register(Project)
admin.site.register(SimulationRun)
admin.site.register(PipelineRun)
admin.site.register(PipelineStep)
