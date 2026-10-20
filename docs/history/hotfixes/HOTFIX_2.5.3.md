# Nikaido DualSense 2.5.3 — Cursor infinito y escape Ctrl + M

## Problema corregido

Mouse → Stick y Mouse → Gyro ya recibían movimiento, pero el cursor físico seguía avanzando hasta tocar el borde del monitor. Los backends basados en posición dejaban de producir deltas en esa dirección y el escritorio quedaba incómodo mientras la captura continuaba activa.

## Solución

- El cursor se centra automáticamente en el monitor de la ventana activa mientras el mouse controla el stick o el gyro virtual.
- Raw Input conserva los deltas relativos aunque Windows recoloque el cursor.
- Los respaldos por hook y sondeo ignoran únicamente el movimiento artificial de recentrado; el movimiento físico sigue llegando al motor.
- La posición anterior del cursor se guarda y se restaura al apagar la captura.
- Un vigilante separado escucha **Ctrl + M** incluso con el juego al frente.
- Ctrl + M apaga únicamente la opción que usa el mouse:
  - KeyBridge: desactiva Mouse → Stick, pero conserva el teclado y el control virtual.
  - Mouse → Gyro: desactiva la fuente de gyro del mouse y conserva el passthrough físico.
- El cambio se sincroniza con la interfaz y con el perfil activo para que no vuelva a activarse solo.

## Seguridad

El vigilante de emergencia no depende del hilo de Raw Input ni del movimiento del cursor. Aunque el juego capture el mouse o este permanezca quieto, Ctrl + M libera el escritorio.

## Validación automática

- 222 pruebas aprobadas.
- Compilación de todos los módulos correcta.
- Pruebas específicas de recentrado, descarte del warp, callback de emergencia y sincronización KeyBridge/Gyro.

## Validación física recomendada

Probar en Windows con uno y varios monitores, tanto en ventana como en pantalla completa. Confirmar que Ctrl + M restaura el cursor y que el eje virtual queda neutral.
