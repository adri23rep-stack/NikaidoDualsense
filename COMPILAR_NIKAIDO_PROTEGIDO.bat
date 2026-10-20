@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
echo ==============================================================
echo  Nikaido DualSense - Compilacion protegida secundaria (Nuitka)
echo ==============================================================
echo.

echo Esta compilacion usa rutas cortas fuera del proyecto para evitar

echo el limite de rutas de Windows al instalar PySide6 y compilar Nuitka.
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10 o superior no esta disponible en PATH.
    echo Instala Python desde python.org y activa "Add Python to PATH".
    pause
    exit /b 1
)

rem Mantener el entorno fuera de Downloads evita rutas mayores de 260 caracteres.
if defined LOCALAPPDATA (
    set "NKB_HOME=%LOCALAPPDATA%\NKB"
) else (
    set "NKB_HOME=%TEMP%\NKB"
)
set "VENV_DIR=%NKB_HOME%\v292"
set "NIKAIDO_PROTECTED_WORKDIR=%NKB_HOME%\w292"
set "PIP_CACHE_DIR=%NKB_HOME%\pip"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%NKB_HOME%" mkdir "%NKB_HOME%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No se pudo crear la carpeta corta: "%NKB_HOME%"
    pause
    exit /b 1
)

if not exist "%VENV_PY%" (
    echo [1/6] Creando entorno protegido corto en:
    echo       %VENV_DIR%
    python -m venv "%VENV_DIR%"
    if errorlevel 1 goto :failed
) else (
    echo [1/6] Reutilizando entorno protegido corto:
    echo       %VENV_DIR%
)

echo [2/6] Actualizando pip y herramientas base...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :failed

echo [3/6] Instalando dependencias protegidas...
"%VENV_PY%" -m pip install --prefer-binary --disable-pip-version-check -r requirements-protected.txt
if errorlevel 1 goto :failed

echo [4/6] Verificando pytest dentro del entorno protegido...
"%VENV_PY%" -c "import pytest; print('      pytest ' + pytest.__version__ + ' listo')"
if errorlevel 1 (
    echo [AVISO] pytest no estaba disponible. Intentando instalarlo...
    "%VENV_PY%" -m pip install --prefer-binary --disable-pip-version-check "pytest>=8,<10"
    if errorlevel 1 goto :failed
)

echo [5/6] Ejecutando pruebas antes de compilar...
"%VENV_PY%" -m pytest -q
if errorlevel 1 goto :failed

echo [6/6] Compilando con Nuitka sin tocar build.py ni release...
echo       Temporales: %NIKAIDO_PROTECTED_WORKDIR%
"%VENV_PY%" build_protected.py
if errorlevel 1 goto :failed

echo.
echo [OK] Salida protegida creada en release_protected.
echo [INFO] El entorno corto se conserva para acelerar la proxima compilacion.
echo [INFO] Puedes borrarlo con LIMPIAR_ENTORNO_PROTEGIDO.bat.
start "" "%CD%\release_protected"
pause
exit /b 0

:failed
echo.
echo [ERROR] La compilacion protegida fallo.
echo La compilacion normal y el codigo fuente no fueron modificados.
echo Entorno usado: "%VENV_DIR%"
echo Temporales: "%NIKAIDO_PROTECTED_WORKDIR%"
pause
exit /b 1
