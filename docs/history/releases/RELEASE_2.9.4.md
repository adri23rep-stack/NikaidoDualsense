# Nikaido DualSense 2.9.4 — auditoría profunda de estabilidad

## Qué cambia

- La conexión HID permite un arranque lento, pero después exige reportes reales para detectar controles dormidos, desconectados o congelados.
- El cierre y la reconexión del DualSense quedan serializados para impedir cierres dobles y estados fantasma.
- La calibración del giroscopio consume únicamente muestras HID nuevas; un mismo paquete repetido ya no completa la calibración ni aprende drift falso.
- Dos macros simultáneas pueden compartir botones, palancas o gatillos sin liberarse entre sí antes de tiempo.
- El cambio de perfil, recarga y cierre cancelan macros activas de forma limpia.
- Los valores analógicos corruptos, infinitos o `NaN` se neutralizan en vez de derribar la ejecución de una macro.
- El puente de vibración virtual vuelve a registrar su callback al reiniciarse y no crea trabajadores duplicados.
- La captura global de mouse, el puente teclado/gamepad, luces, gatillos animados, perfiles automáticos y bandeja quedan protegidos contra arranques simultáneos.
- La ventana oculta de Raw Input ya no intenta destruirse dos veces al cerrar.
- Los paquetes `.Nika` normalizan perfiles, macros, luces, gatillos, gyro e Input Studio antes de guardarse.
- Un paso de macro corrupto se ignora sin perder toda la macro ni cancelar la importación del perfil.
- Las configuraciones dañadas o con números infinitos recuperan valores seguros en vez de cerrar la aplicación.
- Se limpiaron imports muertos, claves duplicadas y pequeñas inconsistencias estáticas.

## Validación automática

- 360 pruebas superadas.
- Compilación de todos los módulos Python superada.
- Ruff sin errores.
- `git diff --check` sin espacios o parches defectuosos.
- 25,000 configuraciones aleatorias probadas contra nueve normalizadores sin caídas.
- Auto‑pruebas portables aprobadas para reporte DS4 extendido, perfiles/rumble/mouse, temas de interfaz y touchpad multizona.
- Bandit: 0 hallazgos graves, 0 medios y 43 avisos bajos revisados.

## Validación pendiente en hardware

Esta revisión se realizó en Linux, por lo que no fue posible confirmar físicamente un DualSense, ViGEm, HidHide, Raw Input ni Bluetooth de Windows. PySide6 tampoco estaba disponible para abrir la interfaz completa. La lógica, simulaciones y pruebas portables están cubiertas, pero antes de publicar el instalador se recomienda ejecutar la lista manual del reporte de auditoría 2.9.4.
