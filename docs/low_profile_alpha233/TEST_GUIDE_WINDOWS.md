# Guía de prueba — Low Profile Alpha 2.3.3

## Objetivo

Comprobar que Nikaido libera la interfaz al minimizar sin apagar la conexión, la emulación ni el perfil activo.

## Prueba rápida

1. Extrae el ZIP completo y ejecuta `INICIAR_NIKAIDO.bat`.
2. En Dashboard confirma que **Low Profile** está activado.
3. Conecta el DualSense y activa la emulación que utilizas normalmente.
4. Abre el Administrador de tareas y anota CPU y memoria de Nikaido.
5. Pulsa el botón minimizar de Nikaido.
6. Confirma que desaparece la ventana y queda el icono en la bandeja.
7. Espera cinco segundos y vuelve a revisar CPU y memoria.
8. Prueba sticks, botones, macros y gyro dentro de un juego.
9. Haz clic en el icono o usa **Abrir Nikaido**. La ventana debe cargarse desde cero y conservar tus ajustes.
10. Repite el ciclo tres veces y finalmente usa **Salir de Nikaido** desde la bandeja.

## Resultado esperado

- La ventana deja de existir mientras Low Profile está activo.
- El control virtual no se desconecta.
- El perfil activo no cambia.
- Los módulos habilitados continúan funcionando.
- Al reabrir, Nikaido vuelve al Dashboard y reconstruye sus páginas bajo demanda.
- No aparecen ventanas duplicadas ni procesos abandonados.

## Datos útiles para reportar

- RAM antes y después de minimizar.
- CPU antes y después de minimizar.
- USB o Bluetooth.
- Emulación Xbox 360 o DualShock 4.
- Si hubo retraso, desconexión o pérdida de configuración.
