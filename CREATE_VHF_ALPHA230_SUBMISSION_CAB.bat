@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Nikaido DualSense Alpha 2.3.0 - Crear CAB sin firma

echo =============================================================
echo  Nikaido DualSense 3.0.0 Alpha 2.3.0 - CAB de presentacion
echo =============================================================
echo.
echo Este comando crea un CAB SIN FIRMA.
echo No consulta certificados, no envia archivos y no modifica Windows.
echo.

call native\vhf\tools\RUN_VHF_SIGNING_TOOL.bat create-submission
set "CREATE_EXIT=%ERRORLEVEL%"
if not "%CREATE_EXIT%"=="0" (
    echo.
    echo [CAB NO GENERADO] Revisa el primer diagnostico anterior.
    echo [SEGURIDAD] No se firmo, envio, instalo ni cargo ningun driver.
    pause
    exit /b %CREATE_EXIT%
)

echo.
echo [OK] Presentacion local sin firma preparada.
echo [BLOQUEADO] No la envies a Partner Center hasta firmar el CAB mediante un proceso autorizado.
echo [IMPORTANTE] El laboratorio nunca accede a tu certificado o clave privada.
pause
exit /b 0
