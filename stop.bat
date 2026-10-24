@echo off
setlocal
cd /d "%~dp0"
title PhD Research Lab - Stopping
call "%~dp0run.bat" --stop %*
