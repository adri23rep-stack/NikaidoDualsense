@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
echo ==============================================================
echo  Nikaido DualSense - Compilar EXE e instalador
echo ==============================================================
call "%~dp0NIKAIDO_RUNTIME.bat"
if errorlevel 1 exit /b 1
if not exist "%VENV_PY%" (
  echo [INFO] Falta el runtime corto. Ejecutando install.bat...
  call install.bat
  if errorlevel 1 exit /b 1
  call "%~dp0NIKAIDO_RUNTIME.bat"
)
"%VENV_PY%" build.py --installer
if errorlevel 1 (
  echo.
  echo [ERROR] No se pudo crear el instalador.
  echo Revisa el mensaje anterior e instala Inno Setup 6 si hace falta.
  pause
  exit /b 1
)
echo.
echo Instalador listo dentro de release.
start "" "%~dp0release"
pause
