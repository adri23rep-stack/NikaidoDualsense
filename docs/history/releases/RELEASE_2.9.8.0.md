# Nikaido DualSense 2.9.8.0 Beta 1

Esta versión pule la salida física del DualSense antes del salto a 3.0. Se centra en luces, batería y gatillos adaptativos sin romper perfiles anteriores.

## Indicador de batería en las luces del jugador

Las luces blancas pueden funcionar como indicador de cuatro niveles:

- 76–100 %: nivel 4;
- 51–75 %: nivel 3;
- 26–50 %: nivel 2;
- 0–25 %: nivel 1;
- batería crítica: parpadeo opcional;
- cargando: animación progresiva opcional;
- carga completa: nivel 4 fijo.

La función no escribe sobre la barra RGB del touchpad. También puede conservar el número de jugador, entregar las luces al juego o apagarlas. Durante el estado inicial 0/desconocido no muestra una alerta falsa de batería crítica.

## Prioridad de RGB

RGB Studio ofrece tres formas de convivencia con los juegos:

- **Prioridad Nikaido:** mantiene vivo el color o efecto seleccionado y lo recupera si otra aplicación lo reemplaza.
- **Equilibrio:** conserva los efectos animados, pero un color fijo se envía una sola vez.
- **Prioridad del juego:** Nikaido deja de escribir en la barra RGB.

Las órdenes internas de RGB y luces de jugador usan el mismo candado HID que el resto del hardware. Esto evita cruces entre servicios propios durante reconexiones. Nikaido no puede impedir que un juego externo escriba al control; los modos deciden si reafirmar la salida o cederla.

## Adaptive Trigger Studio

La página de gatillos se separó en `gui/pages/triggers.py` y ahora incluye:

- biblioteca de 18 presets;
- categorías Básicos, Armas, Vehículos y Mecánicos;
- presets de pistola, rifle, escopeta, francotirador, arco, acelerador, freno, ABS, motor, resorte, máquina y galope;
- monitor en vivo del recorrido físico de L2 y R2;
- resumen legible de fuerza, zonas y vibración;
- botones para probar, limpiar y copiar cada gatillo;
- aplicación de presets a L2, R2 o ambos;
- vinculación real de L2/R2 para presets, perfiles y curvas;
- editor multizona conservado y mejor integrado;
- prueba temporal que restaura el perfil activo.

Todos los presets usan tipos y empaquetados que ya existían en el motor. No se añadieron comandos HID experimentales.

## Compatibilidad

- Conserva perfiles y ajustes anteriores.
- Añade valores predeterminados para `light_control_mode`, `player_led` y `trigger_linked`.
- Mantiene `player_number` como ajuste legado.
- Incluye el nuevo módulo de gatillos en PyInstaller.
- Actualiza versión de aplicación, instaladores y metadatos a 2.9.8.0.

## Validación automatizada

- 453 pruebas aprobadas.
- 2 pruebas omitidas porque PySide6 no está instalado en el entorno de revisión.
- Compilación sintáctica de los módulos modificados aprobada.
- Auditoría de privacidad ejecutada antes del empaquetado.

## Límites de esta revisión

No se realizó una prueba física con un DualSense ni una compilación Windows dentro de este entorno. Los patrones de luces, la sensación de cada preset y la interfaz Qt deben probarse en el equipo real antes de publicar la beta.
