@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo [INFO] CHECK_VHF_ALPHA22_ENVIRONMENT.bat se conserva por compatibilidad.
echo [INFO] Redirigiendo al flujo vigente Alpha 2.3.0.
call CHECK_VHF_ALPHA230_SIGNING_READINESS.bat
exit /b %ERRORLEVEL%
