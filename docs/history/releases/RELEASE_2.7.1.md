# Nikaido DualSense 2.7.1

Hotfix de desconexión física del DualSense sobre la base 2.7.0.

## Cambios

- Detecta reportes HID congelados aunque `pydualsense` conserve el último estado en memoria.
- Usa el contador real del reporte para confirmar que siguen llegando datos del control.
- Declara la desconexión tras 1.5 segundos sin un informe nuevo.
- Limpia batería, botones, sticks, gatillos, touchpad y sensores al desconectar.
- Envía inmediatamente un estado neutral a la interfaz.
- Libera entradas del control virtual para evitar botones o palancas pegadas.
- El wizard de Nikaido vuelve correctamente al estado de búsqueda cuando se desconecta el control.
