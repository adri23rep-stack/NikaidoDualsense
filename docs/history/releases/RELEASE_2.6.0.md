# Nikaido DualSense 2.6.0 — Architecture Foundation

Esta versión reorganiza la interfaz estable de Nikaido 2.5.6 para facilitar el
crecimiento hacia DualSense Edge, controles múltiples y Audio/Haptics Studio.

## Cambios

- `gui/modern_app.py` pasó de 10,984 líneas a una fachada pública pequeña.
- La ventana coordinadora vive en `gui/main_window.py`.
- Las pantallas se dividieron por dominio dentro de `gui/pages`.
- Los componentes compartidos viven en `gui/components.py`.
- Los imports antiguos siguen disponibles desde `gui.modern_app`.
- PyInstaller recopila explícitamente todos los nuevos módulos Qt.
- Las pruebas de código fuente ahora recorren la arquitectura modular y no
  dependen de un archivo monolítico.
- Se añadieron pruebas contra clases duplicadas, crecimiento accidental de la
  fachada y pérdida de módulos durante el empaquetado.

## Compatibilidad

No hay migración de configuración. Los perfiles `.Nika` y la configuración de
2.5.6 se usan sin conversión. El comportamiento visual y funcional debe ser el
mismo; cualquier diferencia se considera un bug.
