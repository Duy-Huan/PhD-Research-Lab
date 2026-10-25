@echo off
setlocal
cd /d "%~dp0"
title PhD Research Lab - Restarting
call "%~dp0run.bat" --restart %*
