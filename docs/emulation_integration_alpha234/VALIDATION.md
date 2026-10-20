# Validación portable — Alpha 2.3.4

## Resultado

- 617 pruebas portables aprobadas.
- 11 pruebas omitidas porque PySide6 no está instalado en este entorno.
- 2 pruebas de importación/arranque Qt deseleccionadas por la misma limitación.
- Compilación sintáctica de los módulos modificados: aprobada.
- Pruebas específicas del Emulation & Integration Hub: aprobadas.
- Pruebas heredadas de Emulación, Low Profile y HID Pump: aprobadas.
- Límite de tamaño por módulo: aprobado; `EmulationPage` vive en `gui/pages/emulation.py`.
- Manifiesto fuente: rutas, tamaños y SHA-256 verificados.
- Auditoría de privacidad: aprobada.

## Pendiente físico

No se afirma prueba visual en Windows, funcionamiento con un DualSense real, ViGEmBus, HidHide, USB/Bluetooth ni compilación del instalador. La prueba final debe realizarse en Windows con PySide6 y el hardware real.
