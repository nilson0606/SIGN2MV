@echo off
setlocal
cd /d "%~dp0"
title SIGN2MV installer
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "RT=%ROOT%\runtime"
rem Keep every cache and temp file inside this folder (not on C:).
set "UV_CACHE_DIR=%RT%\cache\uv"
set "UV_PYTHON_INSTALL_DIR=%RT%\python"
set "UV_PYTHON_BIN_DIR=%RT%\python\bin"
set "UV_TOOL_DIR=%RT%\uv-tools"
set "PIP_CACHE_DIR=%RT%\cache\pip"
set "TEMP=%RT%\tmp"
set "TMP=%RT%\tmp"
set "UV_NO_PROGRESS="
for %%D in ("%RT%" "%RT%\tmp" "%RT%\uv" "%RT%\cache" "%ROOT%\logs") do if not exist "%%~D" mkdir "%%~D"

echo ================================================================
echo  SIGN2MV installer
echo  Folder: %ROOT%
echo  Everything is installed inside this folder.
echo  The first run downloads about 10 GB and can take a long time.
echo  If it stops (for example the network drops), just run it again.
echo ================================================================

if not exist "%RT%\c_free_before.txt" (
  powershell -NoProfile -Command "try { (Get-PSDrive C).Free } catch { '' }" > "%RT%\c_free_before.txt"
)

if exist "%RT%\uv\uv.exe" goto have_uv
echo Downloading uv (Python manager)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $zip='%RT%\tmp\uv.zip'; Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/astral-sh/uv/releases/download/0.13.6/uv-x86_64-pc-windows-msvc.zip' -OutFile $zip; if ((Get-FileHash $zip -Algorithm SHA256).Hash -ne 'A2A8820D5EEA32F08EF467EF3B7F66883A9B076D5737A2FC2FBB5F458D1BB50F') { Remove-Item $zip; exit 3 }; Expand-Archive -Force $zip '%RT%\uv'; Remove-Item $zip"
if errorlevel 1 goto fail_uv
:have_uv

echo Installing Python 3.12 (inside this folder)...
"%RT%\uv\uv.exe" python install 3.12 --no-bin --no-registry
if errorlevel 1 goto fail

if exist "%RT%\envs\server\Scripts\python.exe" goto have_server
"%RT%\uv\uv.exe" venv "%RT%\envs\server" --python 3.12 --seed
if errorlevel 1 goto fail
:have_server
"%RT%\uv\uv.exe" pip install --python "%RT%\envs\server\Scripts\python.exe" -r "%ROOT%\installer\requirements\server.lock.txt"
if errorlevel 1 goto fail

"%RT%\envs\server\Scripts\python.exe" "%ROOT%\installer\install.py" %*
if errorlevel 1 goto fail_quiet
echo.
echo Done. Double-click start.bat to open SIGN2MV.
pause
exit /b 0

:fail_uv
echo ERROR: could not download uv. Check the internet connection, then run install.bat again.
pause
exit /b 1
:fail
echo ERROR: installation step failed. See the messages above and logs\install.log.
echo Run install.bat again after fixing the problem; finished steps are skipped.
:fail_quiet
pause
exit /b 1
