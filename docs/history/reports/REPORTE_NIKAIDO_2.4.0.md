# Reporte Nikaido DualSense 2.4.0

## Implementado

Se añadió **Nikaido KeyBridge**, un motor para convertir teclado y mouse en un control virtual Xbox 360 o DualShock 4.

## Arquitectura

- `src/keyboard_gamepad.py`: configuración, captura global, rampas de ejes, mouse a stick, estado sintético y ciclo de vida.
- `src/emulator.py`: arbitraje de fuente para que solo el DualSense físico o KeyBridge escriban a ViGEm en cada momento.
- `gui/modern_app.py`: panel completo de activación, tipo de control, presets, captura de teclas y ajustes finos.
- `main.py`: creación, restauración, persistencia y apagado ordenado del motor.
- `src/profile_manager.py`: configuración predeterminada y persistente.

## Seguridad de entrada

KeyBridge neutraliza todas las entradas al pausarse o detenerse, apaga el gamepad virtual y devuelve la propiedad del emulador a la fuente DualSense. Esto evita botones pegados, sticks atrapados y dos fuentes escribiendo simultáneamente.

## Validación

- 189 pruebas aprobadas.
- Todos los módulos compilan sintácticamente.
- Pruebas específicas para normalización de teclas, sticks, gatillos, selección DS4/Xbox, ciclo de vida y arbitraje de ViGEm.
- ZIP revisado sin cachés ni artefactos temporales.

## Prueba física pendiente

La salida real DS4/Xbox 360, captura global y ViGEm deben validarse en Windows, ya que el entorno de construcción no tiene Windows ni ViGEmBus disponible.
