# Hotfix 2.5.4 — Cuenta regresiva y Ctrl + M reversible

Este hotfix mejora la experiencia de Mouse → Stick y Mouse → Gyro después de añadir el recentrado automático del cursor.

## Cambios

- Al activar cualquiera de las dos funciones, la captura queda armada durante **5 segundos** antes de comenzar.
- Durante la cuenta el cursor permanece libre para abrir o enfocar el juego.
- Se muestra una ventana flotante grande con los números **5, 4, 3, 2, 1**.
- El aviso permanece por encima de otras ventanas sin robar el foco ni bloquear clics.
- El mensaje explica claramente que **Ctrl + M activa y desactiva el mouse**.
- **Ctrl + M** ahora funciona como interruptor reversible:
  - si la captura está activa, libera el cursor;
  - si está pausada, vuelve a iniciar la cuenta de 5 segundos;
  - no desmarca la opción ni borra la configuración del perfil.
- La interfaz muestra mensajes grandes de **MOUSE ACTIVADO** y **MOUSE LIBERADO**.
- KeyBridge conserva teclado y control virtual al pausar únicamente Mouse → Stick.
- Mouse → Gyro conserva el gyro físico al pausar únicamente la fuente de mouse.
- La escucha del atajo permanece activa aunque la captura esté pausada o Nikaido esté minimizado.

## Seguridad

- La cuenta puede cancelarse antes de capturar el cursor.
- Al cerrar Nikaido o desactivar manualmente la función, se detienen cuenta, captura y escucha global.
- El cursor vuelve a su posición anterior al liberarse, cuando Windows permite restaurarla.

## Validación automática

- Pruebas dedicadas para cuenta regresiva y cancelación.
- Pruebas para estados de KeyBridge y Mouse → Gyro.
- Verificación de la ventana flotante y del interruptor Ctrl + M.
- Compilación completa de módulos y auto-prueba de la rama 2.5.

La validación física final debe hacerse en Windows dentro de un juego, ya que el entorno de construcción no dispone de escritorio Windows, PySide6 ni un DualSense conectado.
