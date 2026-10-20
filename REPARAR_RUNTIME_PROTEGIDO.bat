@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
echo ==============================================================
echo  Nikaido DualSense - Reparar runtime protegido sin recompilar
echo ==============================================================
echo.

if defined LOCALAPPDATA (
    set "NKB_HOME=%LOCALAPPDATA%\NKB"
) else (
    set "NKB_HOME=%TEMP%\NKB"
)
set "VENV_DIR=%NKB_HOME%\v292"
set "NIKAIDO_PROTECTED_WORKDIR=%NKB_HOME%\w292"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo [ERROR] No existe el entorno protegido: "%VENV_DIR%"
    echo Ejecuta primero COMPILAR_NIKAIDO_PROTEGIDO.bat al menos una vez.
    pause
    exit /b 1
)

if not exist "%CD%\release_protected\Nikaido\Nikaido.exe" (
    echo [ERROR] No existe release_protected\Nikaido\Nikaido.exe
    echo Copia este parche dentro del proyecto que ya compilaste.
    pause
    exit /b 1
)

echo [1/2] Copiando ViGEmClient.dll y validando el runtime...
"%VENV_PY%" build_protected.py --repair-runtime-only
if errorlevel 1 goto :failed

echo [2/2] Reparacion terminada.
echo.
echo Prueba ahora:
echo   release_protected\Nikaido\Nikaido.exe
echo.
echo Si abre correctamente, ejecuta CREAR_INSTALADOR_PROTEGIDO.bat
start "" "%CD%\release_protected\Nikaido"
pause
exit /b 0

:failed
echo.
echo [ERROR] No se pudo reparar la salida protegida.
echo No se recompilo Nuitka ni se modifico el codigo fuente original.
pause
exit /b 1
