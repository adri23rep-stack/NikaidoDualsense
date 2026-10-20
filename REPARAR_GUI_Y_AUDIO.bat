@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
echo =====================================================
echo  Nikaido 2.9.8.9 - Reparar GUI y soporte de microfono
echo =====================================================
echo.

call "%~dp0NIKAIDO_RUNTIME.bat"
if errorlevel 1 goto :failed
if not exist "%VENV_PY%" (
    echo No existe el runtime corto de Nikaido.
    echo Se ejecutara install.bat para crearlo e instalar todo.
    call install.bat
    if errorlevel 1 exit /b 1
    exit /b 0
)

echo [1/4] Actualizando herramientas del runtime...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :failed

echo [2/4] Reinstalando GUI y Core Audio sin usar cache...
"%VENV_PY%" -m pip install --upgrade --force-reinstall --no-cache-dir "comtypes>=1.4.10,<2" "pycaw==20251023" "PySide6>=6.8.3,<6.9"
if errorlevel 1 goto :failed
"%VENV_PY%" -m pip install --prefer-binary -r requirements.txt
if errorlevel 1 goto :failed

echo [3/4] Comprobando solo las dependencias del runtime...
if not exist "%CD%\tools\check_runtime_dependencies.py" goto :source_error
"%VENV_PY%" "%CD%\tools\check_runtime_dependencies.py"
if errorlevel 1 goto :dependency_error

echo [4/4] Comprobando por separado el codigo de Nikaido...
"%VENV_PY%" -c "from gui.modern_app import DualSenseGUI; print('[OK] Interfaz de Nikaido disponible')"
if errorlevel 1 goto :source_error

echo.
echo Reparacion completada.
echo Abre siempre INICIAR_NIKAIDO.bat.
pause
exit /b 0

:failed
echo.
echo [ERROR] No se pudo completar la reparacion.
echo Runtime: "%VENV_DIR%"
echo Copia todo el texto de esta ventana para revisarlo.
pause
exit /b 1

:dependency_error
echo.
echo [ERROR] La reparacion de dependencias no quedo completa.
echo [INFO] El codigo del proyecto no se cargo en esta comprobacion.
echo Runtime: "%VENV_PY%"
pause
exit /b 3

:source_error
echo.
echo [ERROR] Las dependencias estan disponibles, pero el codigo de Nikaido no pudo importarse.
echo [INFO] Otra reinstalacion del runtime no corregira este error del proyecto.
echo Proyecto: "%CD%"
echo Runtime: "%VENV_PY%"
pause
exit /b 2
