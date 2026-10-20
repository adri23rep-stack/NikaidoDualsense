@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo [INFO] PREPARE_VHF_ALPHA22_PACKAGE.bat se conserva por compatibilidad.
echo [INFO] Redirigiendo al flujo vigente Alpha 2.3.0.
call PREPARE_VHF_ALPHA230_PACKAGE.bat
exit /b %ERRORLEVEL%
