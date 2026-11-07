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
set "SIGN2MV_EXIT=%errorlevel%"
if not "%SIGN2MV_EXIT%"=="0" pause
exit /b %SIGN2MV_EXIT%
