@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Nikaido DualSense Alpha 2.3.0 - Entorno de firma

echo =============================================================
echo  Nikaido DualSense 3.0.0 Alpha 2.3.0 - Entorno de firma
echo =============================================================
echo.

call native\vhf\tools\RUN_VS2026_WDK_CHECK.bat
set "TOOLCHAIN_EXIT=%ERRORLEVEL%"

echo.
echo Comprobacion de herramientas INF/CAT:
echo.
call native\vhf\tools\RUN_VHF_PACKAGE_TOOL.bat check-tools
set "PACKAGE_EXIT=%ERRORLEVEL%"

echo.
echo Comprobacion de MakeCab y verificacion de firma:
echo.
call native\vhf\tools\RUN_VHF_SIGNING_TOOL.bat check-tools
set "SIGNING_EXIT=%ERRORLEVEL%"

echo.
echo Diagnostico general del laboratorio:
echo.
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -m virtual_dualsense_lab diagnose
) else (
    where python >nul 2>&1
    if not errorlevel 1 python -m virtual_dualsense_lab diagnose
)

echo.
echo [SEGURIDAD] Este comprobador no consulta certificados ni solicita elevacion.
echo [SEGURIDAD] No firma, instala, carga ni cambia protecciones de Windows.
pause
if not "%TOOLCHAIN_EXIT%"=="0" exit /b %TOOLCHAIN_EXIT%
if not "%PACKAGE_EXIT%"=="0" exit /b %PACKAGE_EXIT%
exit /b %SIGNING_EXIT%
