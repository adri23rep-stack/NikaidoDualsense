# Nikaido DualSense 2.9.6.3 — botón MIC como tecla de Windows

Esta versión añade una ruta híbrida para el botón MIC del DualSense cuando el perfil usa **Todos los micrófonos activos**.

## Cambios

- Una pulsación física del botón MIC envía `WM_APPCOMMAND` con `APPCOMMAND_MICROPHONE_VOLUME_MUTE` (24), equivalente a la tecla especial de silencio del micrófono de Windows.
- Después de enviar la orden, Nikaido conserva el motor de Core Audio para forzar el mismo estado en todos los endpoints de captura.
- El mapa de restauración se guarda antes de la orden de Windows, de modo que un cambio inmediato del micrófono predeterminado no contamine el estado original.
- El LED MIC naranja se actualiza inmediatamente y después queda sincronizado con la lectura real de Windows.
- Si Core Audio no consigue iniciar, el botón físico todavía puede enviar la orden de teclado y controlar el LED. La interfaz avisa que el estado no pudo verificarse en todos los dispositivos.
- El botón de la interfaz y las órdenes internas siguen usando Core Audio directamente; no generan una tecla multimedia inesperada.
- El modo **Todos excepto el micrófono del DualSense** permanece en la ruta directa para no silenciar accidentalmente la entrada integrada del control.

## Validación

- 415 pruebas aprobadas.
- 1 prueba de GUI omitida porque PySide6 no está instalado en el entorno de validación.
- El ejecutable de Windows y la entrega real de `WM_APPCOMMAND` deben probarse en una PC con Windows después de compilar.
