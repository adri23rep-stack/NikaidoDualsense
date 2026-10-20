@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Nikaido DualSense - Inicio seguro

echo ==============================================
echo  Nikaido DualSense - Inicio con runtime corto
echo ==============================================
echo.

call "%~dp0NIKAIDO_RUNTIME.bat"
if errorlevel 1 goto :failed

if not exist "%VENV_PY%" (
    echo [INFO] No existe el runtime aislado de Nikaido.
    echo [INFO] Se instalara ahora sin modificar tu Python global.
    call install.bat
    if errorlevel 1 goto :failed
    call "%~dp0NIKAIDO_RUNTIME.bat"
    if errorlevel 1 goto :failed
)

echo [1/4] Comprobando el Python correcto...
"%VENV_PY%" -c "import sys; print('[OK] Runtime:', sys.executable)"
if errorlevel 1 goto :recreate

echo [2/4] Comprobando dependencias de GUI y audio...
if not exist "%CD%\tools\check_runtime_dependencies.py" goto :source_error
"%VENV_PY%" "%CD%\tools\check_runtime_dependencies.py"
if errorlevel 1 goto :repair_dependencies

:verify_gui
echo [3/4] Comprobando el codigo de Nikaido...
"%VENV_PY%" -c "from gui.modern_app import DualSenseGUI; print('[OK] Interfaz de Nikaido disponible')"
if errorlevel 1 goto :source_error

goto :launch

:recreate
echo.
echo [INFO] El runtime corto no puede iniciar. Se reconstruira por completo...
rmdir /s /q "%VENV_DIR%"
call install.bat
if errorlevel 1 goto :failed
call "%~dp0NIKAIDO_RUNTIME.bat"
if errorlevel 1 goto :failed
goto :verify_gui

:repair_dependencies
echo.
echo [INFO] Faltan dependencias del runtime. Reparando sin tocar el codigo ni tus perfiles...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :failed
"%VENV_PY%" -m pip install --prefer-binary --disable-pip-version-check -r requirements-runtime.txt
if errorlevel 1 goto :dependency_error
"%VENV_PY%" "%CD%\tools\check_runtime_dependencies.py"
if errorlevel 1 goto :dependency_error
goto :verify_gui

:launch
echo [4/4] Iniciando Nikaido...
echo.
"%VENV_PY%" "%CD%\main.py" %*
set "NIKAIDO_EXIT=%ERRORLEVEL%"
if not "%NIKAIDO_EXIT%"=="0" (
    echo.
    echo [ERROR] Nikaido termino con codigo %NIKAIDO_EXIT%.
    echo Revisa AppData\DualSenseController\logs para ver el detalle.
    pause
)
exit /b %NIKAIDO_EXIT%

:source_error
echo.
echo [ERROR] Las dependencias estan instaladas, pero el codigo de Nikaido no pudo importarse.
echo [INFO] No se reinstalara el runtime porque eso no corrige errores del proyecto.
echo [INFO] Conserva este texto y revisa que el ZIP se haya extraido completo.
echo Proyecto: "%CD%"
echo Runtime: "%VENV_PY%"
pause
exit /b 2

:dependency_error
echo.
echo [ERROR] El runtime no tiene todas las dependencias necesarias.
echo [INFO] El codigo de Nikaido no se cargo durante esta comprobacion.
echo [INFO] Ejecuta REPARAR_GUI_Y_AUDIO.bat y conserva su diagnostico si vuelve a fallar.
echo Runtime: "%VENV_PY%"
pause
exit /b 3

:failed
echo.
echo [ERROR] No se pudo preparar el runtime corto de Nikaido.
echo Ruta: "%VENV_DIR%"
echo Copia todo el texto de esta ventana para revisarlo.
pause
exit /b 1
