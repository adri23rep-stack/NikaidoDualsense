# Nikaido DualSense 2.9.5 — control de micrófono

## Qué cambia

- El botón físico **MIC** del DualSense silencia o reactiva el micrófono seleccionado en Windows con una sola acción por pulsación.
- El LED naranja se sincroniza con el mute del endpoint de Windows, incluso cuando el estado cambia fuera de Nikaido.
- La ruta de Core Audio vive en un trabajador separado: enumerar o cambiar un dispositivo no bloquea HID, gyro, macros ni emulación.
- La página Audio permite elegir micrófono, actualizar dispositivos, cambiar volumen, mutear y abrir los ajustes de sonido de Windows.
- Cada perfil guarda `enabled`, botón MIC, dispositivo, sincronización del LED, volumen opcional y estado inicial (`conservar`, `silenciado` o `activo`).
- Los paquetes `.Nika` exportan e importan la configuración de audio junto con el resto del perfil.
- Si el dispositivo guardado no está conectado, Nikaido usa temporalmente el micrófono predeterminado y conserva la selección original para cuando vuelva.
- Cambiar una opción del perfil activo no vuelve a forzar el mute o volumen accidentalmente; esas acciones se aplican solamente al cambiar realmente de perfil.
- El cierre restaura el estado MIC del control y libera los endpoints COM en orden seguro.
- Los builds normal y protegido incluyen `pycaw` y `comtypes` y verifican su importación en la auto-prueba.

## Comportamiento predeterminado

1. Conecta el DualSense.
2. Abre **Audio** y deja seleccionado **Predeterminado de Windows** o elige otra entrada.
3. Presiona el botón MIC del control.
4. Windows cambia el mute y el LED naranja refleja el mismo estado.
5. Presiona otra vez para reactivar el micrófono.

## Compatibilidad

La función controla endpoints de captura de Windows. El micrófono integrado del DualSense puede elegirse cuando Windows lo presenta como dispositivo de entrada; también se puede controlar cualquier micrófono USB, de audífonos o integrado en la PC.

## Validación pendiente en hardware

Esta revisión se preparó en Linux. La lógica, persistencia, compatibilidad de la API y estados concurrentes están cubiertos mediante dobles de prueba, pero todavía se debe validar físicamente en Windows con DualSense por USB y Bluetooth, distintos micrófonos y un `.exe` compilado.
