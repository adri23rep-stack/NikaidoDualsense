@echo off
echo [COMPATIBILIDAD] Este nombre pertenece a Alpha 2.
echo [INFO] Alpha 2.3.0 conserva este nombre como acceso compatible.
call "%~dp0BUILD_VHF_ALPHA230.bat" %*
exit /b %ERRORLEVEL%
