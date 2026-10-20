# Emulation & Integration Hub — Alpha 2.3.4

## Objetivo

Convertir la antigua pantalla de Emulación en un centro visual único para DualSense nativo, DualShock 4, Xbox 360 y Nikaido KeyBridge, sin duplicar motores ni tocar la ruta HID de baja latencia.

## Implementación

- Nueva composición de tres columnas: modos, vista dinámica y opciones actuales.
- El `ControllerVisual` cambia emblema central, iluminación y botones según la salida.
- El editor completo de KeyBridge se conserva y se despliega bajo demanda.
- Estado compacto de control físico, salida, dispositivo virtual, latencia interna, conexión, perfil y batería.
- Acciones rápidas: prueba de entrada, prueba de vibración, reinicio virtual y modo pánico.
- HidHide se abre desde Compatibilidad para conservar el flujo seguro existente.
- La fuerza del feedback virtual puede ajustarse desde la nueva pantalla.

## Compatibilidad preservada

- Low Profile y reconstrucción de la interfaz.
- HID Pump de baja latencia.
- Emulación Xbox 360 y DualShock 4.
- Touchpad como mouse.
- Gyro y Mouse → Gyro.
- KeyBridge, presets y editor completo.
- Perfiles `.Nika` y configuración previa.

## Límites

No se afirma validación visual en Windows, prueba física con DualSense, ViGEmBus, HidHide ni compilación del instalador en este entorno. PySide6 no está disponible aquí, por lo que la prueba final de layout debe hacerse en Windows.
