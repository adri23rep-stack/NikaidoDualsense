# Vibración real de gatillos

## Problema corregido

Los perfiles anteriores enviaban los efectos pulsados con el modo `Pulse_A` (`0x22`). Ese modo corresponde a un efecto tipo arco o retorno, no al modo oficial de vibración continua del gatillo. Por eso algunos perfiles mostraban nombres como “vibración” pero no producían la respuesta esperada.

## Motor nuevo

- Los efectos `pulse`, `continuous_vibration` y las armas automáticas usan ahora el modo oficial `Vibration` (`0x26`, expuesto por `pydualsense` como `Pulse_AB`).
- Se empaquetan las 10 zonas del gatillo mediante máscara de activación y amplitudes de 3 bits.
- La frecuencia se envía en el séptimo parámetro que `pydualsense` reserva para el byte de frecuencia.
- Antes de enviar un efecto se limpian los siete parámetros para impedir que sobrevivan bytes de un efecto anterior.

## Vibración adicional por perfil

Cada perfil puede guardar, por separado para L2 y R2:

- Activación o desactivación.
- Intensidad de 0 a 255.
- Frecuencia de 1 a 255 Hz.
- Zona inicial y zona final, de 0 a 9.

Como el DualSense solo admite un modo activo por gatillo, la aplicación mantiene la resistencia base y cambia temporalmente a vibración al cruzar la zona inicial. Al soltar, restaura el efecto original. Se usa histéresis y un pequeño control de tiempo para evitar cambios nerviosos alrededor del umbral.

## Interfaz

- Cada tarjeta de perfil incluye el botón **Vibración**.
- El editor permite configurar y probar L2 y R2 de forma independiente.
- La pestaña **Gatillos** incluye **Probar vibración** para ensayar ambos gatillos sin modificar un perfil.
- El control manual de frecuencia ahora usa el rango real de 1 a 255 Hz.
- Al terminar una prueba se restaura automáticamente el efecto que estaba aplicado.

## Persistencia

Las preferencias se guardan en `settings.profile_trigger_vibration`. Se almacenan aparte para permitir modificar también los perfiles incluidos de fábrica sin convertirlos en perfiles personalizados.

## Pruebas

`tools/test_trigger_vibration.py` valida sin hardware:

- Empaquetado y desempaquetado de zonas.
- Modo `0x26` y frecuencia.
- Serialización de perfiles.
- Guardado y carga de preferencias.
- Prueba temporal y restauración.
- Activación por posición del gatillo.
