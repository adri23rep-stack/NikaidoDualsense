# Reporte de implementación — Nikaido DualSense 2.9.6

## Objetivo

Extender el botón MIC para controlar más que un solo endpoint de Windows, sin romper el
micrófono integrado del DualSense ni activar por accidente entradas que ya estaban silenciadas.

## Modos añadidos

1. **Un micrófono específico**: conserva el comportamiento anterior, incluyendo el dispositivo
   predeterminado de Windows.
2. **Todos los micrófonos activos**: silencia todos los endpoints de captura activos.
3. **Todos excepto el micrófono del DualSense**: excluye nombres habituales como `DualSense` y
   `Wireless Controller`; el LED naranja sigue funcionando, pero la orden enviada al control es
   solo visual y no apaga su micrófono integrado.

## Restauración inteligente

Al comenzar una sesión global se guarda, por ID de endpoint, si cada micrófono ya estaba
silenciado. Al desactivar el mute se restaura ese mapa exacto. Un dispositivo que estaba apagado
antes de la sesión permanece apagado.

La sesión también cubre cambios en caliente:

- Un micrófono conectado después se silencia y se incorpora al mapa de restauración.
- Si Windows o una aplicación reactiva una entrada durante la sesión, Nikaido la vuelve a
  silenciar.
- Si cambia el perfil o el alcance del botón, se restaura primero la sesión global anterior.
- Los IDs desaparecidos no se sustituyen por el dispositivo predeterminado, evitando modificar
  el micrófono equivocado.

## Interfaz y perfiles

La página Audio incluye el selector **Qué silencia el botón MIC**. El selector de dispositivo y
el volumen quedan desactivados cuando el alcance es global. El estado en vivo muestra cuántos
micrófonos están silenciados y distingue estados parciales.

La propiedad `target_mode` se normaliza y viaja en perfiles `.Nika`. Los perfiles antiguos
reciben `selected`, por lo que conservan el comportamiento anterior.

## Robustez adicional

- Enumeración global funcional incluso cuando Windows no entrega un endpoint predeterminado.
- Operaciones parciales continúan con los endpoints válidos y registran los que fallaron.
- Un temporizador de volumen viejo ya no reinicia Core Audio después de cambiar a alcance global.
- La detección del DualSense contempla nombres en inglés, español y portugués.
- Versión actualizada a 2.9.6 en aplicación, proyecto e instaladores.

## Validación

- 401 pruebas aprobadas; una prueba visual omitida porque PySide6 no está instalado en este
  entorno Linux.
- Cinco rondas consecutivas de las 25 pruebas del motor de audio aprobadas.
- Compilación Python completa aprobada.
- Ruff limpio.
- Bandit sin hallazgos medios o graves.
- Auto-pruebas de perfiles/runtime, reporte DS4 extendido, touchpad multizona y temas aprobadas.

## Limitación de esta validación

No fue posible ejecutar Core Audio, pycaw, comtypes ni un DualSense físico dentro de Windows.
La lógica está cubierta con backends simulados, incluyendo endpoints COM, hotplug, restauración,
estados parciales y exclusión del DualSense. La prueba final de hardware debe realizarse en
Windows usando `INICIAR_NIKAIDO.bat`.
