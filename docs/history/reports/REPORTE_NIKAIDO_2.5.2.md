# Reporte de Nikaido DualSense 2.5.2

## Resumen

La versión 2.5.2 corrige la ruta compartida de captura global utilizada por Nikaido KeyBridge y Mouse → Gyro. El fallo estaba concentrado en `src/mouse_to_gyro.py`, por lo que ambas funciones podían quedar sin movimiento aunque sus interruptores estuvieran activos.

## Causa encontrada

1. El capturador dependía únicamente de un hook de bajo nivel basado en posición absoluta.
2. Varias firmas Win32 no declaraban tipos de retorno y argumentos con tamaño de puntero seguro para 64 bits.
3. Los juegos que bloquean o recentran el cursor podían producir deltas nulos o descartados.
4. KeyBridge neutralizaba el mouse completo cuando Nikaido tenía el foco, aunque la opción visual solo prometía ignorar teclas.
5. La interfaz mostraba un estado optimista sin consultar si el capturador realmente estaba vivo.

## Solución aplicada

### `src/mouse_to_gyro.py`

- Reescritura del capturador con Raw Input como backend principal.
- Ventana oculta para recibir `WM_INPUT` sin robar el foco.
- Lectura de movimiento relativo mediante `GetRawInputData`.
- Registro con `RIDEV_INPUTSINK` para recibir movimiento fuera de foco.
- Tipos `WPARAM`, `LPARAM`, handles y callbacks seguros para 64 bits.
- Hook global corregido como segundo backend.
- Sondeo de cursor como respaldo final.
- Estado de backend, errores, paquetes y deltas pendientes.
- Cierre limpio de ventana, hook, hilo y registro Raw Input.

### `src/keyboard_gamepad.py`

- El foco de Nikaido ya no descarta el movimiento del mouse.
- Mientras Nikaido está al frente se vacían únicamente las asignaciones de teclas y clics.
- Diagnóstico ampliado con backend, error y paquetes del mouse.

### `src/emulator.py`

- Nuevo acceso público al estado real de Mouse → Gyro.

### `gui/modern_app.py`

- Estado real de captura en KeyBridge.
- Mensaje visible cuando el mouse no pudo arrancar.
- Backend activo visible en pantalla.
- Texto de la opción de foco corregido.
- Mouse → Gyro deja de informar “listo” cuando no hay captura.

### Empaquetado

- Módulos de KeyBridge y captura de mouse añadidos explícitamente a los imports de PyInstaller.
- Versión 2.5.2 sincronizada en aplicación, paquete e instalador.

## Pruebas añadidas

- Conteo y consumo único de deltas.
- Mouse activo con Nikaido al frente mientras teclas y clics quedan bloqueados.
- Presencia de Raw Input y tipos Win32 de tamaño correcto.
- Diagnóstico público desde el emulador.

## Resultado

```text
215 passed
Auto-prueba: OK
Versión: 2.5.2
```

## Qué probar en Windows

1. Abrir KeyBridge y activar “Mouse → stick derecho”.
2. Confirmar que el estado diga `Raw Input` o alguno de los respaldos.
3. Mover el mouse con Nikaido al frente y revisar el stick derecho en un probador.
4. Probar dentro de un juego que bloquee el cursor.
5. Desactivar KeyBridge, activar DS4 + Passthrough DS4 + Mouse → Gyro.
6. Revisar que la pantalla diga “Captura activa” y que el juego reciba movimiento IMU.
7. Confirmar que F8 neutralice el mouse y que al reanudar no quede ningún eje pegado.
