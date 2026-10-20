@echo off
echo [INFO] Alpha 2.3.0 conserva este nombre como acceso compatible.
call "%~dp0CHECK_VHF_ALPHA230_SIGNING_READINESS.bat" %*
exit /b %ERRORLEVEL%
