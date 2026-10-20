# Nikaido DualSense 2.0.4 — Entrada atómica y giroscopio reconstruido

Este hotfix se concentra en la latencia de botones, el passthrough de movimiento DS4 y la nueva fuente opcional Mouse → Giroscopio.

## Correcciones de baja latencia

- `ConnectionManager` ya no usa el objeto mutable de `pydualsense` mientras otro hilo todavía lo está rellenando.
- Cada tick usa una copia completa del reporte HID para botones, cruceta, palancas, gatillos, touchpad, batería y sensores.
- El reporte coherente pasa primero por los motores de tiempo real y después se envía a ViGEm.
- La interfaz continúa limitada a 60 Hz y no puede frenar la salida virtual de 250 Hz.
- Macros ya no serializa y reconstruye toda la biblioteca en cada paquete.
- Mapper procesa solamente los botones que realmente tienen bindings.

## Giroscopio DS4

- Se corrigió el orden de bytes del DualSense: giroscopio X/Y/Z en 16–21 y acelerómetro X/Y/Z en 22–27.
- El reporte extendido DS4 recibe cada eje desde el mismo paquete físico.
- No hay aprendizaje continuo de ejes mientras se juega.
- La zona muerta solamente neutraliza ruido; no escala ni mezcla el vector.
- Las calibraciones se marcan como versión 3. Las antiguas siguen dentro del perfil, pero no se aplican como centro confiable.

## Mouse → Giroscopio virtual

- Nueva opción apagada por defecto.
- Disponible desde Emulación y Gyro Studio.
- Sensibilidad, inversión horizontal/vertical y combinación con gyro físico.
- El hook descarta eventos inyectados y saltos grandes causados por recenter del cursor.
- Recentrar limpia tanto la IMU temporal como cualquier delta de mouse pendiente.

## Compatibilidad

No cambia el formato `.Nika`, las macros, Input Studio, luces, gatillos ni perfiles existentes. La configuración nueva se guarda dentro del bloque de giroscopio de cada perfil.

## Validación

- 114 pruebas automatizadas aprobadas.
- Compilación sintáctica completa aprobada.
- La validación física final requiere Windows, ViGEm y un DualSense real.
