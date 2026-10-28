@echo off
setlocal
cd /d "%~dp0"
title SIGN2MV
if exist "runtime\envs\server\Scripts\python.exe" goto run
echo SIGN2MV is not installed yet. Double-click install.bat first.
pause
exit /b 1
:run
"runtime\envs\server\Scripts\python.exe" -m app %*
if errorlevel 1 pause
exit /b 0
