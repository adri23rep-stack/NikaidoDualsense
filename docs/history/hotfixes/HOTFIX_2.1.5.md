# Hotfix 2.1.5 — Estado de conexión y batería en el ejecutable

## Problema
El ejecutable empaquetado iniciaba el lector HID más rápido que la interfaz. El DualSense podía conectarse antes de que la ventana registrara sus callbacks, por lo que:

- el control funcionaba normalmente;
- la tarjeta inferior seguía mostrando `Buscando`;
- la batería permanecía en `0 %` hasta cambiar físicamente o reconectar.

## Corrección

- Los nuevos suscriptores de conexión reciben inmediatamente la conexión actual cuando el DualSense ya está activo.
- Los nuevos suscriptores de batería reciben inmediatamente el nivel y estado de carga actuales.
- Los callbacks duplicados no se registran ni se reproducen dos veces.
- La barra lateral se sincroniza además desde cada instantánea HID observada.
- Si un evento inicial se pierde, el siguiente estado recibido corrige automáticamente la conexión y la batería.
- La sincronización visual no muestra notificaciones repetidas ni toca la ruta de baja latencia.

## Compatibilidad

- Sin cambios en `.Nika`.
- Sin cambios en perfiles, macros, giroscopio, mapper o emulación.
- `CONFIG_VERSION` permanece en `2.0.0`.
- `NIKA_FORMAT_VERSION` permanece en `1`.
