# Nikaido DualSense 2.7.2

Esta versión reduce el uso de memoria sin eliminar funciones ni cambiar el formato de perfiles `.Nika`.

## Optimización de RAM

- El wizard ahora se destruye realmente al cerrarse; antes `accept()` podía dejar ocultos sus widgets, sprites y vistas previas.
- Nikaido deja de recargar el mismo sprite cada 700 ms durante la detección del control.
- Sprites, fondos y miniaturas de perfiles se decodifican cerca del tamaño en que se muestran, en lugar de expandirse primero a resolución completa.
- La vista previa del fondo del wizard solo carga la imagen al entrar en Apariencia y la libera al cambiar de paso.
- Las pantallas grandes se importan únicamente al abrirlas, además de seguir construyéndose bajo demanda.
- El caché global de pixmaps queda limitado a 8 MB.
- El historial pasivo de diagnóstico conserva los 10 segundos que usa el reporte y se muestrea a 60 Hz, en vez de construir estructuras en cada tick HID.

## Compatibilidad

- Se conserva el wizard de Nikaido y sus seis escenas.
- Se conserva el hotfix de desconexión física de 2.7.1.
- No cambian perfiles, macros, rutas de AppData, motores ni controles del Dashboard.
- PyInstaller sigue incluyendo todos los módulos Qt aunque ahora se importen bajo demanda.

## Prueba recomendada

Compara el proceso en el Administrador de tareas después de cerrar el wizard, y luego abre varias secciones. Windows puede conservar memoria reservada del runtime, por lo que el valor no siempre baja de inmediato aunque los objetos ya se hayan liberado.
