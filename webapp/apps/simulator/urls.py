from django.urls import path
from . import views

app_name = 'simulator'

urlpatterns = [
    path('', views.index, name='index'),

    # Projects
    path('projects/new/', views.project_new, name='project_new'),
    path('projects/<int:pk>/', views.project_detail, name='project_detail'),
    path('projects/<int:pk>/delete/', views.project_delete, name='project_delete'),

    # Runs
    path('projects/<int:project_pk>/runs/new/', views.run_new, name='run_new'),
    path('runs/<int:pk>/preview/', views.run_preview, name='run_preview'),
    path('runs/<int:pk>/configure/', views.run_configure, name='run_configure'),
    path('runs/<int:pk>/edit-input/', views.run_edit_input, name='run_edit_input'),
    path('runs/<int:pk>/', views.run_detail, name='run_detail'),
    path('runs/<int:pk>/status/', views.run_status_api, name='run_status_api'),
    path('runs/<int:pk>/sources/', views.run_sources_api, name='run_sources_api'),
    path('runs/<int:pk>/launch/', views.run_launch, name='run_launch'),
    path('runs/<int:pk>/download/csv/', views.download_csv, name='download_csv'),
    path('runs/<int:pk>/download/zip/', views.download_zip, name='download_zip'),
    path('runs/<int:pk>/copy/', views.run_copy, name='run_copy'),
    path('runs/<int:pk>/delete/', views.run_delete, name='run_delete'),

    # Scenarios comparison
    path('projects/<int:pk>/scenarios/', views.project_scenarios, name='project_scenarios'),
    path('projects/<int:pk>/scenarios/csv/', views.scenarios_download_csv, name='scenarios_download_csv'),

    # Pipelines
    path('projects/<int:project_pk>/pipelines/new/', views.pipeline_new, name='pipeline_new'),
    path('pipelines/<int:pk>/', views.pipeline_detail, name='pipeline_detail'),
    path('pipelines/<int:pk>/status/', views.pipeline_status_api, name='pipeline_status_api'),
    path('pipelines/<int:pk>/launch/', views.pipeline_launch, name='pipeline_launch'),
    path('pipelines/<int:pk>/copy/', views.pipeline_copy, name='pipeline_copy'),
    path('pipelines/<int:pk>/delete/', views.pipeline_delete, name='pipeline_delete'),
]
