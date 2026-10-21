@echo off
rem PhD Research Lab command-line client (shares the backend with the browser UI). Usage: phdlab --help
setlocal
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
set "PYTHONIOENCODING=utf-8"
"%PY%" -m backend.cli %*
