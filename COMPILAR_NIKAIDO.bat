@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
echo ==========================================
echo  Nikaido DualSense - Compilacion segura
echo ==========================================
echo.
call "%~dp0NIKAIDO_RUNTIME.bat"
if errorlevel 1 exit /b 1
if not exist "%VENV_PY%" (
    echo [INFO] Falta el runtime corto. Ejecutando install.bat...
    call install.bat
    if errorlevel 1 exit /b 1
    call "%~dp0NIKAIDO_RUNTIME.bat"
)
"%VENV_PY%" build.py
if errorlevel 1 (
    echo.
    echo [ERROR] La compilacion fallo. Revisa el mensaje anterior.
    pause
    exit /b 1
)
echo.
echo Abriendo la carpeta release...
start "" "%~dp0release"
pause
