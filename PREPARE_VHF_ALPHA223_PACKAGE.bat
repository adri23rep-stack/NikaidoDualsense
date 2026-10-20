@echo off
echo [INFO] Alpha 2.3.0 conserva este nombre como acceso compatible.
call "%~dp0PREPARE_VHF_ALPHA230_PACKAGE.bat" %*
exit /b %ERRORLEVEL%
