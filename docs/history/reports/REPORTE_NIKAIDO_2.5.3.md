# Reporte de Nikaido DualSense 2.5.3

## Resumen

La versión 2.5.3 completa el arreglo de mouse iniciado en 2.5.2. La captura ya funcionaba, pero el cursor podía llegar al borde de la pantalla y limitar los backends que dependen de posición absoluta. Ahora Nikaido ofrece movimiento continuo y una salida de emergencia global.

## Cambios técnicos

### `src/mouse_to_gyro.py`

- Vigilante independiente `NikaidoMouseSafety`.
- Centrado periódico con `SetCursorPos` en el monitor de la ventana activa.
- Compatibilidad con escritorios de varios monitores mediante `MonitorFromWindow` y métricas del escritorio virtual como respaldo.
- Conservación y restauración de la posición original del cursor.
- Filtro de un solo warp para que el recentrado no se convierta en movimiento de stick/gyro.
- Detección global de Ctrl + M mediante `GetAsyncKeyState`.
- Callback de apagado de emergencia y diagnóstico de conteo, motivo, centro y hotkey.

### `src/keyboard_gamepad.py`

- Ctrl + M cambia `mouse_stick_enabled` a falso.
- Neutraliza únicamente los ejes del mouse del stick derecho.
- KeyBridge, teclado y botones permanecen activos.
- Diagnóstico ampliado con centrado y salida de emergencia.

### `src/emulator.py` y `src/gyro_engine.py`

- Mouse → Gyro publica el apagado de emergencia.
- GyroEngine actualiza su configuración real y notifica el cambio al perfil activo.
- El gyro físico y el DS4 virtual no se apagan por liberar el mouse.

### `gui/modern_app.py`

- Indicaciones visibles de Ctrl + M.
- Checkbox sincronizado cuando el apagado ocurre fuera de la interfaz.
- Guardado automático de Mouse → Stick desactivado.
- Aviso breve cuando el cursor queda liberado.

## Pruebas añadidas

- Estado de centrado y hotkey.
- Descarte del movimiento artificial de warp.
- Conservación de deltas físicos.
- Callback de Ctrl + M ejecutado una sola vez.
- Neutralización y apagado de Mouse → Stick.
- Sincronización del perfil de Mouse → Gyro.
- Presencia de las APIs de cursor y del vigilante global.

## Resultado

```text
222 passed
Versión: 2.5.3
```

## Prueba manual sugerida

1. Activar KeyBridge y Mouse → Stick.
2. Mover el mouse continuamente hacia la misma dirección durante varios segundos.
3. Confirmar que el stick sigue respondiendo y el cursor permanece centrado.
4. Presionar Ctrl + M y comprobar que el cursor vuelve a su posición anterior.
5. Confirmar que KeyBridge sigue activo, pero Mouse → Stick queda desmarcado.
6. Repetir con DS4 virtual, Passthrough DS4 y Mouse → Gyro.
7. Probar en pantalla completa y, si existe, en un segundo monitor.
