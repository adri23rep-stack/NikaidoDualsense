# Validación portable — Alpha 2.3.1 Input Latency Hotfix

## Resultados confirmados en el entorno de revisión

- Compilación sintáctica de `src/connection_manager.py`: aprobada.
- Pruebas enfocadas de conexión, desconexión, diagnóstico y pipeline: aprobadas.
- Suite portable completa sin las dos pruebas que requieren importar PySide6: **605 aprobadas, 11 omitidas y 2 deseleccionadas**.
- Las dos pruebas deseleccionadas dependen de PySide6, paquete no instalado en el entorno de revisión; no fallaron por el hotfix.
- Simulación de reportes físicos a 250 Hz durante 0.75 s:
  - procesamiento: aproximadamente 251 Hz;
  - snapshots nuevos: aproximadamente 251 Hz;
  - estados reutilizados: 0;
  - p95 del pipeline simulado: aproximadamente 0.037 ms.
- Prueba de bloqueo: sostener el candado de salidas físicas no detiene el snapshot de entrada.
- Prueba de carrera: una desconexión neutraliza ViGEm y un tick viejo no puede sobrescribirla.

## Límites

El entorno de revisión no tiene DualSense físico, ViGEmBus ni Windows. La mejora debe confirmarse en Windows comparando USB y Bluetooth. Las cifras anteriores validan el programador y el orden de ejecución, no afirman una medición física de extremo a extremo.

## Qué observar en Windows

En el Centro de diagnóstico revisar:

- `low_latency_scan_active = true` mientras la emulación esté activa;
- `low_latency_scan_hz = 1000`;
- `processing_hz` y `fresh_snapshot_hz` cercanos a la tasa real del control;
- `snapshot_to_virtual_p95_ms` y `button_edge_p95_ms`;
- ausencia de tirones al usar RGB, vibración o gatillos simultáneamente.
