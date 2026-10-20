# Nikaido DualSense 2.1.0

La versión 2.1 agrega tres sistemas completos sobre la base estable de 2.0.4. No cambia el formato `.Nika` ni elimina ajustes anteriores.

## Centro de diagnóstico

- métricas de HID, ViGEm y latencia interna de lectura a salida virtual;
- promedio, p95 y máximo para detectar picos;
- paquetes perdidos, duplicados, lectura cruda y fallback;
- vista de botones y valores físicos en vivo;
- captura de sesiones cortas;
- detección de posibles capas de entrada duplicada;
- reporte técnico sanitizado en ZIP.

## Mapper avanzado por perfil

- editor visual de capas y gestos;
- pulsar, mantener, soltar, corto, largo, doble y alternar;
- doble pulsación exclusiva;
- acciones de control, teclado, mouse, macro, perfil, capa y gyro;
- combinaciones mediante condiciones;
- turbo y bloqueo selectivo;
- seguridad al cambiar de perfil durante una pulsación;
- capas apiladas sin quedarse en la capa incorrecta al soltar botones fuera de orden;
- datos incluidos automáticamente al exportar un perfil `.Nika`.

## Gyro Aim y Flick Stick

- controles generales y avanzados reorganizados;
- presets prácticos;
- activación con cualquier botón;
- sensibilidad y respuesta separadas por eje;
- Flick Stick para mouse y stick virtual;
- telemetría de ángulo y giro pendiente;
- configuración completamente separada por perfil.

## Compatibilidad

- `CONFIG_VERSION` se mantiene en `2.0.0` para no forzar una migración destructiva.
- `NIKA_FORMAT_VERSION` se mantiene en `1`; el mapper avanzado es un campo adicional compatible dentro de `profile.json`.
- el mapa avanzado global de 2.0 se conserva como respaldo para perfiles que todavía no tengan configuración propia.
- los modos nuevos llegan apagados o con valores seguros en perfiles antiguos.
