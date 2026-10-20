@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title Nikaido DualSense - Instalacion segura

echo ===============================================
echo  Nikaido DualSense - Entorno aislado y corto
echo ===============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10 o superior no esta disponible en PATH.
    echo Instala Python desde python.org y activa "Add Python to PATH".
    pause
    exit /b 1
)

call "%~dp0NIKAIDO_RUNTIME.bat"
if errorlevel 1 (
    echo [ERROR] No se pudo preparar la carpeta corta del runtime.
    pause
    exit /b 1
)

echo [INFO] Proyecto: %CD%
echo [INFO] Runtime corto: %VENV_DIR%
echo.
if exist ".venv\Scripts\python.exe" (
    echo [AVISO] Se encontro una .venv antigua dentro del proyecto.
    echo         Nikaido ya no la usara porque puede romper PySide6 en rutas largas.
    echo         Puedes borrarla cuando quieras; perfiles y ajustes no estan ahi.
    echo.
)

rem Si Windows o Python se actualizaron, una venv vieja puede conservar el EXE
rem pero ya no iniciar. Solo borramos el runtime administrado, nunca el proyecto.
if exist "%VENV_PY%" (
    "%VENV_PY%" -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
    if errorlevel 1 (
        echo [INFO] El runtime corto esta danado o pertenece a otro Python.
        echo [INFO] Se reconstruira sin tocar perfiles ni configuraciones.
        rmdir /s /q "%VENV_DIR%"
        if exist "%VENV_PY%" goto :failed
    )
)

if not exist "%VENV_PY%" (
    echo [1/7] Creando entorno virtual corto...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 goto :failed
) else (
    echo [1/7] Reutilizando entorno virtual corto.
)

echo [2/7] Comprobando la version de Python...
"%VENV_PY%" -c "import sys; assert sys.version_info >= (3, 10), 'Se requiere Python 3.10 o superior'; print('[OK]', sys.executable); print('[OK]', sys.version)"
if errorlevel 1 goto :failed

echo [3/7] Actualizando pip y herramientas base...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :failed

echo [4/7] Instalando dependencias con ruedas binarias...
"%VENV_PY%" -m pip install --prefer-binary --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :failed

echo [5/7] Verificando dependencias HID, GUI y audio...
if not exist "%CD%\tools\check_runtime_dependencies.py" goto :source_error
"%VENV_PY%" "%CD%\tools\check_runtime_dependencies.py"
if errorlevel 1 goto :dependency_error

echo [6/7] Verificando el codigo de Nikaido...
"%VENV_PY%" -c "from gui.modern_app import DualSenseGUI; print('[OK] Interfaz de Nikaido disponible')"
if errorlevel 1 goto :source_error

echo [7/7] Preparando configuracion del usuario...
if not exist "%APPDATA%\DualSenseController" mkdir "%APPDATA%\DualSenseController"

echo.
echo ==========================================
echo  INSTALACION COMPLETADA
echo ==========================================
echo Abre siempre: INICIAR_NIKAIDO.bat
echo Runtime usado: %VENV_DIR%
echo Compilar: COMPILAR_NIKAIDO.bat
pause
exit /b 0

:source_error
echo.
echo [ERROR] Las dependencias se instalaron correctamente, pero el codigo de Nikaido no pudo importarse.
echo [INFO] Reinstalar paquetes no corregira este error. Verifica que el ZIP se haya extraido completo.
echo Proyecto: "%CD%"
echo Runtime: "%VENV_PY%"
pause
exit /b 2

:dependency_error
echo.
echo [ERROR] La instalacion termino, pero una o mas dependencias no pueden cargar.
echo [INFO] El codigo de Nikaido aun no se importo; este es un fallo del runtime.
echo [INFO] Ejecuta REPARAR_GUI_Y_AUDIO.bat y conserva su diagnostico si vuelve a fallar.
echo Runtime: "%VENV_PY%"
pause
exit /b 3

:failed
echo.
echo [ERROR] La instalacion no pudo completarse.
echo Runtime usado: "%VENV_DIR%"
echo Proyecto: "%CD%"
echo.
echo Si el intento anterior dejo una .venv incompleta dentro del proyecto,
echo puedes borrarla. Esta version no la utiliza.
echo Copia todo el texto de esta ventana para revisarlo.
pause
exit /b 1
