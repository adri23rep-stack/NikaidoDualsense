# Reporte de entrega — Nikaido DualSense 2.5.0

## Resultado

Se construyó la primera base robusta de Nikaido 2.5 sobre el proyecto 2.4.0 KeyBridge. La actualización conserva las funciones existentes y agrega tres bloques principales: vibración devuelta por los juegos, perfiles automáticos avanzados y un centro de compatibilidad con HidHide.

## 1. Vibración del juego al DualSense físico

Se añadió un puente independiente que recibe los motores enviados al control virtual Xbox 360 o DualShock 4 y los reproduce en el DualSense físico.

Incluye:

- Fuerza global y fuerza separada por motor.
- Opción para intercambiar motores.
- Suavizado configurable para evitar cambios bruscos.
- Apagado de seguridad cuando dejan de llegar eventos.
- Neutralización al cerrar, desconectar o cambiar la emulación.
- Hilo separado para que el feedback no bloquee la lectura del control.
- Estado en vivo y errores visibles dentro de Vibración y Diagnóstico.

Archivos principales:

- `src/virtual_feedback.py`
- `src/emulator.py`
- `src/diagnostics.py`
- `gui/modern_app.py`

## 2. Perfiles automáticos 2.0

El sistema anterior por proceso fue ampliado a reglas editables desde la interfaz.

Cada regla puede usar:

- Ejecutable o ruta completa.
- Texto del título de la ventana.
- Prioridad.
- Detección únicamente cuando el juego está al frente o mientras siga abierto.
- Retrasos de entrada y salida para evitar saltos nerviosos.
- Perfil de destino.

También se agregó:

- Restauración del perfil anterior al salir del juego.
- Respeto a un cambio manual de perfil hecho por el usuario.
- Historial y estado en vivo.
- Compatibilidad con la configuración antigua por nombre de proceso.
- Persistencia dentro del perfil `.Nika`.

Archivos principales:

- `src/game_profile_watcher.py`
- `gui/modern_app.py`
- `main.py`

## 3. Centro de compatibilidad e HidHide

Se añadió una sección dedicada a prevenir la doble entrada causada por tener visibles al mismo tiempo el DualSense físico y el control virtual.

Incluye:

- Detección de instalación y estado de HidHide.
- Detección de Nikaido en la lista de aplicaciones permitidas.
- Estado del ocultamiento global.
- Lista de dispositivos DualSense reconocidos.
- Selección y confirmación antes de ocultar un dispositivo.
- Acceso al cliente oficial e instalación mediante herramientas de Windows.
- Diagnóstico de riesgo de doble entrada.

La integración es conservadora: usa las herramientas oficiales de HidHide y no modifica el controlador ni el registro de forma directa.

Archivos principales:

- `src/hidhide_manager.py`
- `gui/modern_app.py`
- `src/diagnostics.py`

## 4. Calidad, mantenimiento y distribución

También se añadieron mejoras para que el proyecto sea más fácil de mantener y publicar:

- Versión actualizada a `2.5.0`.
- Instalador opcional con Inno Setup 6.
- `CREAR_INSTALADOR.bat`.
- Archivo `LICENSE` MIT.
- `pyproject.toml`.
- Flujo de pruebas automático para Windows en `.github/workflows/quality.yml`.
- Auto-prueba rápida en `tools/nikaido_25_selftest.py`.
- Documentación separada para las funciones nuevas.
- Nuevos módulos de backend separados de la interfaz principal.

## 5. Validaciones realizadas

| Validación | Resultado |
|---|---:|
| Suite automatizada | 207 pruebas aprobadas |
| Compilación de módulos Python | Correcta |
| Auto-prueba Nikaido 2.5 | Correcta |
| Apertura real de Perfiles automáticos en Qt | Correcta |
| Apertura real de Compatibilidad/HidHide en Qt | Correcta |
| Apertura real de Vibración en Qt | Correcta |
| Compatibilidad con pruebas anteriores | Correcta |

La prueba visual de Qt se ejecutó sin pantalla mediante el modo `offscreen`, creando las páginas con dependencias simuladas y procesando sus eventos reales.

## 6. Pruebas nuevas

- `tests/test_virtual_feedback_250.py`
- `tests/test_emulator_feedback_250.py`
- `tests/test_game_profile_watcher_250.py`
- `tests/test_hidhide_manager_250.py`
- `tests/test_main_250_integration.py`
- `tests/test_ui_250_source.py`
- Pruebas adicionales del instalador en `tests/test_build_distribution.py`.

## 7. Validaciones pendientes antes de publicación pública

Este entorno no tiene Windows, ViGEmBus, HidHide ni un DualSense físico. Por eso todavía deben comprobarse en una PC real:

1. Vibración de juegos con emulación Xbox 360 y DS4.
2. Vibración por USB y Bluetooth durante sesiones largas.
3. Reconexión del control mientras llega feedback.
4. Ocultamiento y restauración de dispositivos reales con HidHide.
5. Compilación del `.exe` e instalador final en Windows.
6. Cambio automático entre varios juegos, launchers y ventanas sin bordes.

No se añadió un actualizador por internet porque el proyecto todavía no tiene definido un repositorio público o una dirección oficial de lanzamientos. Agregar uno sin una fuente firmada sería inseguro.

## 8. Deuda técnica que sigue abierta

`gui/modern_app.py` continúa siendo un archivo grande, con aproximadamente 10,700 líneas. La lógica pesada nueva sí quedó separada en módulos, pero conviene dividir las páginas de la interfaz en archivos individuales durante una actualización posterior, después de validar esta versión en hardware. Hacer esa mudanza al mismo tiempo que la integración de feedback y HidHide habría aumentado innecesariamente el riesgo de regresiones.

## Estado recomendado

**Nikaido DualSense 2.5.0 — candidata de prueba en hardware.**

La lógica, la interfaz y las pruebas están cerradas. Tras superar la matriz real de Windows/USB/Bluetooth, puede marcarse como lanzamiento estable.
