# Nikaido DualSense 2.5.2 — Hotfix de captura de mouse

## Problemas corregidos

- KeyBridge no recibía movimiento del mouse para el stick derecho.
- Mouse → Gyro podía mostrarse activado sin recibir movimiento real.
- La opción para ignorar teclas con Nikaido al frente también neutralizaba accidentalmente el movimiento del mouse.
- La captura anterior dependía de un hook de Windows con firmas débiles en sistemas de 64 bits.

## Cambios principales

### Captura global robusta

`MouseGyroSource` ahora intenta tres rutas en este orden:

1. **Raw Input de Windows** mediante `RegisterRawInputDevices`, `WM_INPUT` y `GetRawInputData`.
2. **Hook global de bajo nivel** como respaldo.
3. **Sondeo del cursor** como último respaldo para escritorio.

Las firmas Win32 usan tamaños de puntero correctos para Windows de 64 bits y conservan las referencias de callbacks y ventanas durante toda la captura.

### KeyBridge

- El movimiento del mouse sigue activo aunque Nikaido tenga el foco.
- Las teclas y clics asignados continúan bloqueados con la opción de enfoque.
- El estado muestra el backend real: Raw Input, hook global o sondeo.
- Si el mouse no inicia, ahora aparece el error exacto en rojo.
- Se muestran contadores internos de paquetes para diagnóstico.

### Mouse → Gyro

- La pantalla comprueba el estado real del capturador.
- Ya no muestra “listo” si el backend no arrancó.
- Informa el método de captura activo o el error de Windows.

### Distribución

- `src.keyboard_gamepad` y `src.mouse_to_gyro` se incluyen explícitamente en PyInstaller.
- Aplicación, paquete e instalador actualizados a 2.5.2.

## Validación automática

- 215 pruebas aprobadas.
- Compilación de módulos correcta.
- Auto-prueba 2.5 aprobada, incluida la ruta de deltas del mouse.

## Validación física pendiente

El comportamiento final debe comprobarse en Windows con un mouse real, ViGEmBus y un juego o probador de mando. El entorno de desarrollo de esta revisión no ejecuta Windows ni dispone de hardware físico.
