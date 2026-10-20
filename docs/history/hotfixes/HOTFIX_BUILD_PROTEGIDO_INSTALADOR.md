# Hotfix del instalador protegido — Nikaido DualSense 2.9.2

## Problema corregido

La compilación protegida ya utilizaba el entorno corto `%LOCALAPPDATA%\NKB\v292`, pero `CREAR_INSTALADOR_PROTEGIDO.bat` todavía buscaba la antigua `.venv` local y ejecutaba nuevamente pruebas y una compilación completa con Nuitka.

## Solución

- `CREAR_INSTALADOR_PROTEGIDO.bat` reutiliza el entorno corto existente.
- Comprueba que `release_protected\Nikaido\Nikaido.exe` exista.
- Comprueba que Inno Setup 6 esté instalado.
- Crea el instalador desde la distribución ya compilada, sin volver a ejecutar Nuitka.
- Se añadió `build_protected.py --installer-only`.
- El instalador resultante se guarda en `release_protected\Nikaido_DualSense-2.9.2-Protected-Setup.exe`.

## Flujo correcto

1. Ejecutar `COMPILAR_NIKAIDO_PROTEGIDO.bat`.
2. Probar `release_protected\Nikaido\Nikaido.exe`.
3. Ejecutar `CREAR_INSTALADOR_PROTEGIDO.bat`.
4. Probar el instalador en Windows.
