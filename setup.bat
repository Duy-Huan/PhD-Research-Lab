@echo off
setlocal
cd /d "%~dp0"
echo === PhD Interactive Autonomous Research Lab - setup ===
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% --version || (echo Python 3.10+ is required: https://www.python.org/downloads/ & pause & exit /b 1)
if not exist .venv\Scripts\python.exe %PY% -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt || (echo Dependency install failed. & pause & exit /b 1)
if not exist references mkdir references
echo.
echo Setup complete. Start the app with run.bat
pause
