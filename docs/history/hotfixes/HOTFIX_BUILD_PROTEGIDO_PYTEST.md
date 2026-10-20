# Hotfix del compilador protegido: pytest ausente

## Problema

El entorno corto de la compilación protegida instalaba las dependencias de
ejecución y Nuitka, pero no instalaba `pytest`. El proceso llegaba al paso de
pruebas y terminaba con `No module named pytest`.

## Solución

- `requirements-protected.txt` incluye ahora `pytest>=8,<10`.
- El BAT verifica que `pytest` pueda importarse antes de ejecutar la suite.
- Si un entorno reutilizado todavía no lo tiene, intenta instalarlo de forma
  automática y muestra un error claro si la instalación falla.
- El código fuente, la compilación normal y los perfiles del usuario no se
  modifican.

## Uso

Extrae este paquete y ejecuta nuevamente `COMPILAR_NIKAIDO_PROTEGIDO.bat`. El
entorno existente en `%LOCALAPPDATA%\NKB\v292` puede reutilizarse; no hace
falta borrarlo.
