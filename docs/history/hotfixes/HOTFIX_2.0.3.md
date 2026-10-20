# Nikaido DualSense 2.0.3 — Ajuste de giroscopio DS4

## Alcance

Este hotfix modifica únicamente la ruta del giroscopio en **passthrough DS4**. No cambia la barra lateral, la optimización de sticks, perfiles, macros, RGB ni Input Studio.

## Problema corregido

El centrado automático de la versión anterior todavía podía tomar muestras mientras el mando estaba empezando a moverse. En ciertas condiciones eso provocaba que un movimiento principal de pitch (arriba/abajo) arrastrara pequeñas lecturas de yaw o roll y el juego recibiera una diagonal o un giro lateral inesperado.

## Cambios

- El centro automático se calcula una sola vez al activar el passthrough y después queda congelado.
- Pitch, yaw y roll se validan y centran de manera independiente.
- El acelerómetro impide aceptar el centro mientras el control se está inclinando.
- La calibración guardada en el perfil tiene prioridad absoluta y ya no se vuelve a aprender durante la partida.
- Una compuerta conservadora elimina solamente fugas laterales diminutas; los movimientos diagonales reales se conservan.
- Se mantiene una zona neutral pequeña para evitar ruido del sensor en reposo.

## Compatibilidad

- `CONFIG_VERSION` permanece en **2.0.0**.
- El formato `.Nika` permanece en la versión **1**.
- No se modifican perfiles, macros ni configuraciones existentes.

## Validación

- **102 pruebas aprobadas**.
- Pruebas específicas para aislamiento de ejes, centro inicial, inclinación durante el arranque y respeto de la calibración del perfil.
- Compilación sintáctica completa sin errores.

La comprobación final de dirección y sensación necesita Windows, ViGEm y un DualSense físico.
