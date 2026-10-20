# Validación — Alpha 2.3.2 Low-Latency HID Pump

## Pruebas enfocadas

- 15 pruebas aprobadas.
- Incluye publicación del último reporte crudo, normalización Bluetooth, diagnóstico de la bomba y una escritura física simulada de 50 ms que no detiene las lecturas HID.

## Suite portable completa

- 609 pruebas aprobadas.
- 11 omitidas porque PySide6 no está instalado en este entorno.
- 2 pruebas de arranque/importación de GUI deseleccionadas por la misma ausencia de PySide6.
- Sin fallos en la ruta de entrada, ViGEm, macros, perfiles, gyro, manifiestos, privacidad ni laboratorio nativo.

## Límites

No se dispone de Windows, DualSense físico ni ViGEmBus en este entorno. La mejora final debe confirmarse en USB y Bluetooth. Esta validación no afirma una medición física de latencia.
