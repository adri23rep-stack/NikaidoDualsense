@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo [INFO] BUILD_VHF_ALPHA222.bat se conserva por compatibilidad.
echo [INFO] Redirigiendo al flujo vigente Alpha 2.3.0.
call BUILD_VHF_ALPHA230.bat
exit /b %ERRORLEVEL%
