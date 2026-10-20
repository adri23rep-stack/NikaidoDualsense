@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Nikaido DualSense Alpha 2.3.0 - Verificar respuesta Microsoft

echo =============================================================
echo  Nikaido DualSense 3.0.0 Alpha 2.3.0 - Verificacion firmada
echo =============================================================
echo.
echo Este comando es de solo lectura y NO instala el driver.
echo.

if "%~1"=="" (
    echo [USO] VERIFY_VHF_ALPHA230_MICROSOFT_RETURN.bat "C:\Ruta\PaqueteExtraido"
    echo [INFO] La carpeta debe contener INF, SYS y CAT devueltos por Microsoft.
    pause
    exit /b 2
)

call native\vhf\tools\RUN_VHF_SIGNING_TOOL.bat verify-return "%~1"
set "VERIFY_EXIT=%ERRORLEVEL%"
if not "%VERIFY_EXIT%"=="0" (
    echo.
    echo [VERIFICACION RECHAZADA] No instales ni cargues ese paquete.
    echo [SEGURIDAD] No se modifico Windows.
    pause
    exit /b %VERIFY_EXIT%
)

echo.
echo [OK] Verificacion criptografica y de procedencia aprobada.
echo [BLOQUEADO] Este paso no instala ni enumera el dispositivo.
pause
exit /b 0
