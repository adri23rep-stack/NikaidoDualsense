@echo off
rem Ruta corta compartida por instalacion, inicio, compilacion y diagnostico.
rem Mantener PySide6 fuera de Downloads evita el limite historico de 260 caracteres.

if defined NIKAIDO_RUNTIME_HOME (
    set "NKB_HOME=%NIKAIDO_RUNTIME_HOME%"
) else if defined LOCALAPPDATA (
    set "NKB_HOME=%LOCALAPPDATA%\NKB"
) else (
    set "NKB_HOME=%TEMP%\NKB"
)

set "VENV_DIR=%NKB_HOME%\rt"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "PIP_CACHE_DIR=%NKB_HOME%\pip"
set "NIKAIDO_VENV_DIR=%VENV_DIR%"
set "NIKAIDO_SHORT_TEMP=%NKB_HOME%\tmp"

if not exist "%NKB_HOME%" mkdir "%NKB_HOME%" >nul 2>&1
if errorlevel 1 exit /b 1
if not exist "%PIP_CACHE_DIR%" mkdir "%PIP_CACHE_DIR%" >nul 2>&1
if not exist "%NIKAIDO_SHORT_TEMP%" mkdir "%NIKAIDO_SHORT_TEMP%" >nul 2>&1

rem pip descomprime archivos QML muy profundos; usar tambien un temporal corto.
set "TEMP=%NIKAIDO_SHORT_TEMP%"
set "TMP=%NIKAIDO_SHORT_TEMP%"
exit /b 0
