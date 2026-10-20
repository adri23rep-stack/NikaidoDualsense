# Hotfix 2.1.1 — Diagnóstico confiable

Este hotfix corrige únicamente el Centro de diagnóstico y su telemetría. No modifica la ruta funcional del passthrough DS4, las curvas, el mapper, las macros ni el rendimiento que ya funcionaba en 2.1.0.

## Correcciones principales

### Frecuencia física correcta

El número de secuencia Sony ya no se interpreta como si cada salto fuera una pérdida. Nikaido mantiene un contador acumulado y calcula la frecuencia física con el avance entre dos instantes. Esto permite reconocer correctamente un DualSense cercano a 250 Hz aunque la aplicación observe menos copias distintas.

### Sin falsos paquetes perdidos

Los saltos pequeños se clasifican como **informes intermedios reemplazados**. Significan que el dispositivo publicó varios estados y Nikaido conservó el más reciente antes del siguiente tick. `lost_reports` se mantiene en cero únicamente como campo compatible; el reporte declara que no existe detección confirmada de pérdidas a ese nivel.

Los saltos enormes se consideran reinicios o discontinuidades del contador y nunca se convierten en miles de pérdidas falsas.

### Frecuencias separadas

El panel muestra por separado:

- HID físico estimado;
- procesamiento de Nikaido;
- estados nuevos observados;
- control virtual ViGEm;
- Gyro Engine procesado.

### Gyro Engine

La frecuencia visible del gyro se calcula con una ventana de secuencias nuevas. Los callbacks muy cercanos ya no producen valores imposibles de 500 Hz o más.

### Latencia de botones

Se añadió promedio, p95 y máximo para ticks donde cambió al menos un botón. Así el reporte puede confirmar específicamente la ruta de pulsación/liberación, además de la latencia general.

### Captura física y virtual

Cada muestra incluye:

- entrada física;
- salida efectiva enviada al control virtual;
- tiempos de lectura, motores en tiempo real, ViGEm y copia física → salida virtual;
- secuencia y fuente para comprobar que ambos estados pertenecen al mismo tick.

### Salud y avisos

- Los informes intermedios no reducen la salud.
- No tener una calibración permanente en passthrough DS4 aparece como aviso informativo, porque existe centrado temporal.
- Solo fallos reales de lectura, frecuencia física anormalmente baja, picos altos, errores de ViGEm o conflictos confirmados afectan la salud.

## Compatibilidad

- `CONFIG_VERSION` permanece en `2.0.0`.
- `.Nika` permanece en versión 1.
- Los alias `poll_hz`, `unique_hid_hz`, `duplicate_reports` y `lost_reports` siguen presentes para lectores antiguos.
- Los campos planos de `capture.json` siguen disponibles junto con las nuevas secciones `physical`, `virtual` y `timing`.
