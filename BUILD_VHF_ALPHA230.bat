@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Nikaido DualSense Alpha 2.3.0 - Compilar fuente con VS2026

echo =============================================================
echo  Nikaido DualSense 3.0.0 Alpha 2.3.0 - Compilacion fuente
echo =============================================================
echo.
echo Este comando solo compila. No empaqueta, firma, instala ni carga el driver.
echo.

call native\vhf\tools\RUN_VHF_PACKAGE_TOOL.bat clear-build-record
set "CLEAR_RECORD_EXIT=%ERRORLEVEL%"
if not "%CLEAR_RECORD_EXIT%"=="0" (
    echo.
    echo [ERROR DE REGISTRO] No se pudo invalidar el comprobante de la compilacion anterior.
    echo [SEGURIDAD] Compilacion cancelada para no reutilizar un resultado viejo.
    pause
    exit /b 32
)

call native\vhf\tools\RUN_VS2026_WDK_CHECK.bat
set "TOOLCHAIN_EXIT=%ERRORLEVEL%"
if not "%TOOLCHAIN_EXIT%"=="0" (
    echo.
    echo [DEPENDENCIA FALTANTE] Compilacion cancelada antes de ejecutar MSBuild.
    echo [INFO] El comprobador anterior identifica el componente exacto que falta.
    pause
    exit /b %TOOLCHAIN_EXIT%
)

echo.
echo [1/2] Compilando driver KMDF/VHF con WindowsKernelModeDriver10.0...
msbuild native\vhf\driver\NikaidoVirtualHid.vcxproj /m /t:Rebuild /nologo /p:Configuration=Release /p:Platform=x64
set "DRIVER_EXIT=%ERRORLEVEL%"
if not "%DRIVER_EXIT%"=="0" (
    echo.
    echo [ERROR DE COMPILACION - DRIVER] MSBuild fallo con codigo %DRIVER_EXIT%.
    echo [INFO] Revisa el primer error: puede corresponder al proyecto, al codigo o a una tarea del WDK.
    echo [SEGURIDAD] No se instalo ni cargo ningun resultado parcial.
    pause
    exit /b 30
)

echo.
echo [2/2] Compilando cliente de diagnostico con PlatformToolset v145...
msbuild native\vhf\client\NikaidoVhfClient.vcxproj /m /t:Rebuild /nologo /p:Configuration=Release /p:Platform=x64
set "CLIENT_EXIT=%ERRORLEVEL%"
if not "%CLIENT_EXIT%"=="0" (
    echo.
    echo [ERROR DE COMPILACION - CLIENTE] MSBuild fallo con codigo %CLIENT_EXIT%.
    echo [INFO] El driver compilo, pero el cliente no; no prepares ningun paquete.
    echo [SEGURIDAD] No se instalo ni cargo ningun resultado.
    pause
    exit /b 31
)

echo.
call native\vhf\tools\RUN_VHF_PACKAGE_TOOL.bat record-build
set "RECORD_EXIT=%ERRORLEVEL%"
if not "%RECORD_EXIT%"=="0" (
    echo.
    echo [ERROR DE REGISTRO] La compilacion termino, pero no se pudieron guardar sus hashes.
    echo [BLOQUEADO] No prepares el paquete hasta repetir una compilacion correcta.
    pause
    exit /b 32
)

echo.
echo [OK] Driver, PDB y cliente compilados por MSBuild.
echo [OK] Fuentes, driver y PDB registrados mediante hashes.
echo [OK] La ruta PDB incrustada en el SYS se limita al nombre del archivo.
echo [SIGUIENTE] Ejecuta PREPARE_VHF_ALPHA230_PACKAGE.bat.
echo [BLOQUEADO] Los binarios locales no estan firmados ni autorizados para instalarse.
echo [IMPORTANTE] Compilar no demuestra enumeracion HID ni compatibilidad con juegos.
pause
exit /b 0
