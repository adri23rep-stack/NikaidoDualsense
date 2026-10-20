# Reporte técnico — Nikaido DualSense 2.1.1

## Objetivo

Corregir las métricas falsas detectadas en los reportes reales de la versión 2.1.0 sin alterar el comportamiento del control, el passthrough DS4 ni la ruta de baja latencia.

## Evidencia usada

El reporte proporcionado mostraba 330 muestras en aproximadamente 9.985 segundos. Al desenvolver el contador Sony, este avanzó 2,494 posiciones: **249.77 informes por segundo**. El diagnóstico 2.1.0 mostraba 67.49 Hz y 20,300 pérdidas porque confundía estados no observados individualmente con pérdidas del bus.

## Cambios de arquitectura

### `src/connection_manager.py`

- Ventana de progreso `(tiempo, contador acumulado)` para estimar `device_report_hz`.
- Métricas separadas `processing_hz` y `fresh_snapshot_hz`.
- `coalesced_reports` para estados intermedios reemplazados.
- `sequence_discontinuities` para reinicios o saltos grandes.
- `button_edge_avg_ms`, `button_edge_p95_ms` y `button_edge_max_ms`.
- `snapshot_to_virtual_avg_ms` y p95.
- Último desglose temporal disponible para las capturas.
- Alias antiguos conservados para compatibilidad.

### `src/emulator.py`

- Copia ligera del último estado efectivo enviado a ViGEm.
- Incluye botones físicos/remapeados/macros, sticks, gatillos, modo, secuencia y marca temporal.
- Neutralización explícita al desconectar o cambiar de modo.

### `src/gyro_engine.py`

- Frecuencia calculada con secuencias nuevas en una ventana estable.
- Los callbacks agrupados o repetidos no inflan la cifra.
- No se cambió el algoritmo de salida del gyro.

### `src/diagnostics.py`

- Formato de reporte versión 2.
- Definiciones de métricas incluidas en `report.json`.
- Capturas con secciones `physical`, `virtual` y `timing`.
- Salud basada en fallos verificables.
- Avisos informativos separados de los problemas.
- Resumen de texto actualizado.

### Interfaz

- 16 tarjetas con nombres y tooltips claros.
- Se eliminan “Paquetes perdidos” y “HID único” como etiquetas engañosas.
- El dashboard muestra fallos de lectura reales.

## Validación

- 135 pruebas automatizadas aprobadas.
- Compilación sintáctica completa.
- Pruebas nuevas para una fuente de 250 Hz observada mediante saltos de secuencia.
- Prueba de que 20,000 estados intermedios no degradan la salud.
- Prueba de captura física/virtual con tiempos coincidentes.
- Prueba de frecuencia del gyro resistente a callbacks agrupados.

## Límites honestos

La aplicación no puede confirmar pérdidas físicas del bus usando solamente la última copia expuesta por pydualsense. Por esa razón el hotfix no inventa una cifra de pérdida: muestra fallos reales de lectura, discontinuidades y estados intermedios reemplazados como categorías separadas.
