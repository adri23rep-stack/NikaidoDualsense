@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Nikaido DualSense 3.0.0 Alpha 2.3.0 - Microsoft Signing Readiness

echo =============================================================
echo  Nikaido DualSense 3.0.0 Alpha 2.3.0 - Microsoft Signing Readiness
echo =============================================================
echo.
echo Herramienta independiente. No instala drivers ni cambia Windows.
echo.

where py >nul 2>&1
if not errorlevel 1 goto :run_py

where python >nul 2>&1
if not errorlevel 1 goto :run_python

echo [ERROR] Se requiere Python 3.10 o superior.
echo [INFO] El laboratorio no instalara Python ni ningun driver automaticamente.
pause
exit /b 1

:run_py
py -3 -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if errorlevel 1 goto :python_version_error
if "%~1"=="" (
    py -3 -m virtual_dualsense_lab diagnose
) else (
    py -3 -m virtual_dualsense_lab %*
)
set "LAB_EXIT=%ERRORLEVEL%"
goto :finished

:run_python
python -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if errorlevel 1 goto :python_version_error
if "%~1"=="" (
    python -m virtual_dualsense_lab diagnose
) else (
    python -m virtual_dualsense_lab %*
)
set "LAB_EXIT=%ERRORLEVEL%"
goto :finished

:python_version_error
echo [ERROR] El Python detectado es anterior a 3.10 o no puede iniciar.
echo [INFO] No se modifico el runtime estable de Nikaido.
pause
exit /b 2

:finished
echo.
if not "%LAB_EXIT%"=="0" echo [ERROR] El laboratorio termino con codigo %LAB_EXIT%.
pause
exit /b %LAB_EXIT%
