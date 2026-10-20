@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Nikaido - Diagnostico Audio y HidHide

call "%~dp0NIKAIDO_RUNTIME.bat"
if errorlevel 1 goto :failed
if not exist "%VENV_PY%" (
    echo [ERROR] No existe el runtime corto de Nikaido.
    echo Ejecuta primero INICIAR_NIKAIDO.bat o install.bat.
    pause
    exit /b 1
)

"%VENV_PY%" tools\diagnose_audio_hidhide.py
set "EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%EXIT_CODE%"=="0" echo El diagnostico termino con errores.
pause
exit /b %EXIT_CODE%

:failed
echo [ERROR] No se pudo preparar la ruta del runtime.
pause
exit /b 1
