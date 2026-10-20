@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Nikaido DualSense Alpha 2.3.0 - Preparar paquete sin firma

echo =============================================================
echo  Nikaido DualSense 3.0.0 Alpha 2.3.0 - Paquete INF/CAT
echo =============================================================
echo.
echo Este comando valida y genera un catalogo SIN FIRMA.
echo No instala, carga, firma ni registra el driver.
echo.

call native\vhf\tools\RUN_VS2026_WDK_CHECK.bat
set "TOOLCHAIN_EXIT=%ERRORLEVEL%"
if not "%TOOLCHAIN_EXIT%"=="0" (
    echo.
    echo [DEPENDENCIA FALTANTE] Empaquetado cancelado antes de leer artefactos.
    pause
    exit /b %TOOLCHAIN_EXIT%
)

echo.
call native\vhf\tools\RUN_VHF_PACKAGE_TOOL.bat check-tools
set "PACKAGE_CHECK_EXIT=%ERRORLEVEL%"
if not "%PACKAGE_CHECK_EXIT%"=="0" (
    echo.
    echo [DEPENDENCIA DE PAQUETE] Falta una herramienta concreta del WDK.
    echo [INFO] No repares componentes que el comprobador marco como disponibles.
    pause
    exit /b %PACKAGE_CHECK_EXIT%
)

echo.
echo [1/3] Verificando el registro de compilacion por hashes...
echo [2/3] Validando INF Universal con InfVerif...
echo [3/3] Comprobando firmabilidad y generando CAT sin firma con Inf2Cat...
call native\vhf\tools\RUN_VHF_PACKAGE_TOOL.bat prepare
set "PREPARE_EXIT=%ERRORLEVEL%"
if not "%PREPARE_EXIT%"=="0" (
    echo.
    echo [PAQUETE NO GENERADO] Revisa el primer diagnostico anterior.
    echo [SEGURIDAD] No se instalo, cargo ni firmo ningun resultado.
    pause
    exit /b %PREPARE_EXIT%
)

echo.
echo [OK] Paquete sin firma preparado y manifestado.
echo [SIGUIENTE] Ejecuta CREATE_VHF_ALPHA230_SUBMISSION_CAB.bat.
echo [BLOQUEADO] No lo instales: falta una firma aceptada por Microsoft.
echo [IMPORTANTE] InfVerif e Inf2Cat no demuestran enumeracion HID ni estabilidad en kernel.
pause
exit /b 0
