@echo off
cd /d %~dp0
echo Iniciando servidor Django PYQ2K...
echo Abre http://127.0.0.1:8000 en tu navegador
echo.
..\\.venv\Scripts\python.exe manage.py runserver
pause
