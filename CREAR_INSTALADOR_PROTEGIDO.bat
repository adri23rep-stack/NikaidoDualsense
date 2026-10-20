@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
echo ==============================================================
echo  Nikaido DualSense - Instalador de compilacion protegida
echo ==============================================================
echo.

if not exist "release_protected\Nikaido\Nikaido.exe" (
    echo [ERROR] No existe la compilacion protegida terminada.
    echo Ejecuta primero COMPILAR_NIKAIDO_PROTEGIDO.bat y espera el mensaje de exito.
    pause
    exit /b 1
)

if defined LOCALAPPDATA (
    set "NKB_HOME=%LOCALAPPDATA%\NKB"
) else (
    set "NKB_HOME=%TEMP%\NKB"
)
set "VENV_PY=%NKB_HOME%\v292\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo [ERROR] No existe el entorno protegido corto:
    echo         %VENV_PY%
    echo Ejecuta primero COMPILAR_NIKAIDO_PROTEGIDO.bat.
    pause
    exit /b 1
)

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo [ERROR] Inno Setup 6 no esta instalado.
    echo Descargalo e instalalo y vuelve a ejecutar este archivo.
    pause
    exit /b 1
)

echo [1/2] Verificando compilacion protegida existente...
"%VENV_PY%" -c "from pathlib import Path; p=Path(r'release_protected\Nikaido\Nikaido.exe'); assert p.is_file(); print('      Nikaido.exe listo')"
if errorlevel 1 goto :failed

echo [2/2] Creando instalador sin recompilar Nuitka...
"%VENV_PY%" build_protected.py --installer-only
if errorlevel 1 goto :failed

echo.
echo [OK] Instalador protegido creado en release_protected.
start "" "%CD%\release_protected"
pause
exit /b 0

:failed
echo.
echo [ERROR] No se pudo crear el instalador protegido.
pause
exit /b 1
