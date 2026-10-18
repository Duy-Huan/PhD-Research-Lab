@echo off
setlocal
cd /d "%~dp0"
echo === PhD Interactive Autonomous Research Lab v3.0 - setup ===
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% --version || (echo Python 3.10+ is required: https://www.python.org/downloads/ & pause & exit /b 1)
if not exist .venv\Scripts\python.exe %PY% -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt || (echo Dependency install failed. & pause & exit /b 1)
if not exist references mkdir references
if not exist data mkdir data

echo.
echo === Optional tools (each one only enables a feature; nothing is changed on your PC) ===
call :tool docker     "Docker Desktop (Code IDE sandbox, GPU containers)" "https://www.docker.com/products/docker-desktop/"
call :tool git        "Git for Windows (Source Control, Publish to GitHub)" "https://git-scm.com/download/win"
call :tool nvidia-smi "NVIDIA driver (GPU passthrough into Docker)"         "https://www.nvidia.com/Download/index.aspx"
call :tool ollama     "Ollama (local AI, recommended)"                      "https://ollama.com/download"
call :tool lms        "LM Studio CLI (lets the app load LM Studio models)"  "in LM Studio: Developer tab, enable the lms CLI"
call :tool latexmk    "LaTeX - MiKTeX or TeX Live (PDF preview)"            "https://miktex.org/download"
where docker >nul 2>nul
if errorlevel 1 goto :afterdocker
docker info >nul 2>nul
if errorlevel 1 echo   NOTE: Docker is installed but not running - start Docker Desktop before using the Code IDE.
:afterdocker

echo.
echo Setup complete. Start the app with run.bat
echo After it opens, the Docker ^& System tab scans this PC and offers a recommended setup.
pause
exit /b

:tool
where %1 >nul 2>nul
if errorlevel 1 goto :toolmissing
echo   [OK]      %~2
exit /b
:toolmissing
echo   [missing] %~2  -  %~3
exit /b
