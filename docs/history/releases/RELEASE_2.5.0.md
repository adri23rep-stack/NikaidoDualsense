# Nikaido DualSense 2.5.0 — Base robusta

## Vibración real desde los juegos

- Captura el feedback enviado por juegos a Xbox 360 o DualShock 4 virtual.
- Devuelve golpes y vibración fina al DualSense físico.
- Fuerza global y por motor, intercambio, suavizado y timeout de seguridad.
- Neutralización automática al cambiar de modo, desconectar o cerrar.
- Telemetría dentro del Centro de diagnóstico.

## Perfiles automáticos 2.0

- Detección de la ventana en primer plano.
- Reglas por ejecutable, ruta y título de ventana.
- Prioridades y retrasos para evitar cambios nerviosos.
- Modo “solo al frente” o “mientras esté abierto”.
- Restauración del perfil anterior.
- Respeto a cambios manuales durante una regla.
- Compatibilidad con el mapa antiguo de perfiles por proceso.

## Compatibilidad e HidHide

- Nueva pantalla para detectar doble entrada.
- Instalación, cliente oficial, lista permitida y estado de ocultamiento.
- Selección explícita antes de ocultar o mostrar un dispositivo.
- Sin cambios directos al driver ni borrado de configuraciones ajenas.

## Calidad y distribución

- Instalador opcional con Inno Setup 6.
- Licencia incluida, `pyproject.toml` y flujo de pruebas para Windows.
- Nuevos módulos separados para feedback e HidHide.
- Auto-prueba `tools/nikaido_25_selftest.py`.
- Diagnóstico ampliado con feedback, automatización e HidHide.
- 207 pruebas automatizadas al cerrar esta versión de trabajo.

## Validación pendiente en hardware

Las pruebas automatizadas validan lógica y seguridad, pero la vibración real, HidHide y el instalador deben probarse también en Windows con ViGEmBus, un DualSense físico y al menos un juego que produzca rumble.
