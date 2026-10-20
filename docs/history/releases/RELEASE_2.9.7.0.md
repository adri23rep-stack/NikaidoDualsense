# Nikaido DualSense 2.9.7.0 Beta 1

Esta versión congela funciones nuevas y fortalece la aplicación para una primera beta pública.

## Vibración compilada

La página de Vibración ya no hace una escritura aislada. Ahora inicia una prueba manual con prioridad temporal, reafirma ambos motores mientras dura y evita que el feedback de Xbox/DS4 la apague. La misma ruta limita valores, registra errores y expone diagnóstico.

## Asistente

La biblioteca creció a más de treinta consejos sobre perfiles, HidHide, macros, gyro, vibración, audio, actualizaciones y diagnóstico. Una bolsa mezclada conserva los consejos pendientes en la configuración para no repetirlos en cada inicio. El sonido corto puede desactivarse sin apagar los consejos.

## Actualizaciones

La edición independiente incluye un motor que:

- consulta un manifiesto JSON por HTTPS;
- distingue canal estable y beta;
- compara versiones;
- valida producto, tamaño y SHA-256;
- descarga de forma atómica;
- abre el instalador sobre la instalación existente;
- conserva configuración, perfiles, macros e imágenes guardados fuera de la carpeta del programa.

La URL pública no se incluye hasta que Team Nikaido publique un servidor o una release oficial. Sin URL, la comprobación queda desactivada y Ajustes lo explica claramente.

## Privacidad e identidad pública

El código, metadatos de Windows, instaladores, EULA, documentación, pruebas y diagnósticos usan únicamente **Team Nikaido**. No se incluye información personal del desarrollador. Esta beta no tiene firma digital, así que Windows puede mostrar “Editor desconocido”.

Los builds normal y protegido ejecutan `tools/privacy_audit.py` antes de empaquetar. La compilación se cancela si detecta el usuario del equipo, su carpeta personal o términos añadidos mediante `NIKAIDO_PRIVACY_TERMS`.

## Diagnóstico

El Centro de diagnóstico puede copiar un resumen sanitizado al portapapeles, además del ZIP de soporte existente.

## Validación

La suite automatizada cubre prioridad de vibración, repetición temporal, metadatos públicos, consejos, manifiestos, comparación de versiones, descarga y verificación SHA-256.
