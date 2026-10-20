# Nikaido DualSense — Input Latency Hotfix

## Diagnóstico

La ruta anterior esperaba el periodo completo de 4 ms antes de consultar el último reporte del DualSense. En Windows esa espera puede despertar tarde, y durante ese tiempo pueden acumularse varios reportes físicos. Además, el candado que protegía la lectura también se usaba para luces, vibración, micrófono y gatillos; una escritura física lenta podía detener el envío a ViGEm.

## Cambios

- Escaneo ligero del contador Sony a 1 kHz solo cuando el gamepad virtual está activo.
- La ruta completa se ejecuta al detectar un reporte nuevo o cada 4 ms como heartbeat.
- `timeBeginPeriod(1)` durante la ejecución en Windows y restauración con `timeEndPeriod(1)` al cerrar.
- Prioridad `ABOVE_NORMAL` para el hilo lector; no se utiliza `TIME_CRITICAL`.
- Entrada virtual separada del candado de salidas físicas.
- Candado independiente para ordenar macros, gyro, ViGEm y neutralización.
- Generación de conexión para rechazar snapshots pertenecientes a una sesión desconectada.
- Observadores de interfaz limitados a 60 Hz; macros, remapeo y ViGEm conservan la ruta rápida.

## Archivos principales

- `src/connection_manager.py`
- `tests/test_input_latency_hotfix_alpha230.py`
- `INPUT_LATENCY_HOTFIX_PROJECT.json`
