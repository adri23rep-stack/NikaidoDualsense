@echo off
setlocal EnableExtensions EnableDelayedExpansion

where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
    if not errorlevel 1 (
        py -3 "%~dp0signing_readiness.py" %*
        exit /b !ERRORLEVEL!
    )
)

where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
    if not errorlevel 1 (
        python "%~dp0signing_readiness.py" %*
        exit /b !ERRORLEVEL!
    )
)

echo [DEPENDENCIA FALTANTE] Se requiere Python 3.10 o superior para el comprobador.
echo [INFO] No se instalara ni reparara ningun runtime automaticamente.
exit /b 19
