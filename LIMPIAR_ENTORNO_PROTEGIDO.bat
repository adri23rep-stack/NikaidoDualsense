@echo off
setlocal EnableExtensions
chcp 65001 >nul

if defined LOCALAPPDATA (
    set "NKB_HOME=%LOCALAPPDATA%\NKB"
) else (
    set "NKB_HOME=%TEMP%\NKB"
)

echo ==============================================================
echo  Nikaido - Limpiar entorno de compilacion protegida
echo ==============================================================
echo.
echo Se eliminara: "%NKB_HOME%"
echo La salida release_protected y el codigo del proyecto NO se borraran.
echo.
choice /C SN /N /M "Continuar? [S/N]: "
if errorlevel 2 exit /b 0

if exist "%NKB_HOME%" (
    rmdir /s /q "%NKB_HOME%"
    if errorlevel 1 (
        echo [ERROR] No se pudo eliminar todo. Cierra Python, Nuitka y el Explorador.
        pause
        exit /b 1
    )
)
echo [OK] Entorno protegido eliminado.
pause
exit /b 0
