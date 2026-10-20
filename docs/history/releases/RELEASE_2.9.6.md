# Nikaido DualSense 2.9.6 — mute global de micrófonos

## Nueva función

La página Audio ahora permite elegir qué controla el botón MIC:

- Un micrófono específico o el predeterminado de Windows.
- Todos los micrófonos de captura activos.
- Todos los micrófonos excepto la entrada integrada del DualSense.

## Restauración segura

Al activar el mute global, Nikaido guarda el estado previo de cada endpoint. Al volver a
presionar MIC, restaura individualmente esos estados; un micrófono que ya estaba silenciado
no se reactiva por accidente.

Durante una sesión global activa, los micrófonos conectados después o reactivados desde
Windows se silencian automáticamente y se agregan a la restauración. Si se cambia de perfil
o alcance, Nikaido restaura primero la sesión anterior para no dejar entradas atoradas.

## DualSense

El modo `todos excepto DualSense` excluye los endpoints cuyos nombres corresponden al
DualSense o a `Wireless Controller`. El LED naranja sigue el estado global, pero Nikaido usa
solo la orden del LED y no silencia físicamente el micrófono integrado del control.

## Compatibilidad

La nueva propiedad `target_mode` se normaliza, se guarda por perfil y viaja dentro del formato
`.Nika`. Los perfiles anteriores continúan funcionando y reciben `selected` como valor seguro.
