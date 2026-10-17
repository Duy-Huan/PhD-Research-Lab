@echo off
setlocal
cd /d "%~dp0"
title PhD Research Lab

if not exist "backend\app.py" goto :notextracted

rem ---- pick a Python: project venv > py launcher > python on PATH
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY (
  where py >nul 2>nul && set "PY=py -3"
)
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY goto :nopython

echo Using Python: %PY%
%PY% start.py %*
echo.
echo ------------------------------------------------------------
echo Server stopped. If you saw an [ERROR] above, copy this whole
echo window text and send it for help.
echo ------------------------------------------------------------
pause
exit /b

:notextracted
echo [ERROR] backend\app.py not found.
echo Please EXTRACT the zip first: right-click the zip - Extract All,
echo then run run.bat from the extracted folder.
pause
exit /b 1

:nopython
echo [ERROR] Python not found. Install Python 3.11 or 3.12 from
echo https://www.python.org/downloads/  and tick "Add python.exe to PATH".
pause
exit /b 1
