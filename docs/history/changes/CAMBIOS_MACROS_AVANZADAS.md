# Nikaido DualSense v1.3.0 — Macros avanzadas

## Biblioteca de macros

- Nueva biblioteca con búsqueda, detalles, estado activo/pausado y cantidad de macros disponibles en el perfil actual.
- Crear, editar, duplicar, probar, detener y eliminar macros.
- Importación y exportación en archivos `*.nikaido-macro.json`.
- Plantillas editables para toques rápidos, combos, flicks de palanca, gatillos progresivos y fuego rápido.

## Activadores

Una macro puede ejecutarse mediante:

- Un botón físico.
- Un combo de varios botones.
- Una dirección de la palanca izquierda o derecha.
- Un nivel de presión de L2 o R2.
- El botón manual **Probar**.

También puede ejecutarse al presionar, al soltar o repetirse mientras el activador se mantiene.

## Secuencias

Las secuencias aceptan:

- Tocar un botón durante un tiempo configurable.
- Presionar y mantener un botón.
- Soltar un botón.
- Combos simultáneos.
- Movimientos de ambas palancas mediante selector visual X/Y.
- Presión analógica de L2 y R2.
- Esperas explícitas.

Cada acción tiene un campo **Después** para modificar directamente el tiempo antes de la siguiente acción. El botón **Intervalo…** permite aplicar el mismo tiempo a toda la secuencia.

## Grabación

La grabación desde el DualSense ahora captura:

- Botones.
- Palancas.
- Gatillos analógicos.
- Tiempo real entre cada entrada.

Los tiempos grabados quedan compactados en cada acción para que sean fáciles de editar.

## Perfiles y compatibilidad

- Cada macro puede funcionar en todos los perfiles o solo en perfiles seleccionados.
- Hay accesos rápidos para usar el perfil actual, seleccionar todos o limpiar la selección.
- Las macros de versiones anteriores siguen cargando mediante migración automática.
- Los antiguos campos `trigger_button` y `delay_ms` siguen siendo compatibles.
