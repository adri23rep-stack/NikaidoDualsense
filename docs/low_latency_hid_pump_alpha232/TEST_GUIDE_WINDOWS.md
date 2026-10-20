# Prueba en Windows — Alpha 2.3.2

1. Extrae el ZIP completo y ejecuta `INICIAR_NIKAIDO.bat`.
2. Conecta por USB, activa emulación Xbox 360 y prueba primero sin Steam Input.
3. Repite con RGB, vibración y gatillos activos.
4. En Diagnóstico confirma que `hid_input_pump.installed`, `active` y `output_thread_active` sean `true`.
5. `input_reports` debe subir rápido; `physical_output_writes` debe subir mucho más lento que `input_reports`.
6. Repite por Bluetooth.
7. Si el lag continúa, genera un reporte de diagnóstico después de mover ambas palancas y pulsar Cross diez veces.

No uses dos emuladores simultáneos. Para Fallout 4, desactiva Steam Input durante esta prueba para evitar una segunda capa de traducción.
