# Nikaido DualSense 2.2.0

## Nikaido Nexus

- Nuevo espacio visual para diseñar el comportamiento del DualSense.
- Control dibujado con botones seleccionables y contadores de acciones.
- Inspector por botón con creación, edición, duplicado y eliminación.
- Atajos para teclado, macros, capas, gyro, desactivar y passthrough.
- Nexus Flow para navegar las capas del perfil y revisar su cantidad de acciones.
- Reutiliza el motor de capas y gestos existente; no duplica la lógica de remapeo.

## Personalización visual

- Fondo personalizado elegido por el usuario.
- Copia segura del fondo a AppData.
- Vista previa dentro de Ajustes.
- Oscurecimiento y zoom configurables.
- Transparencia independiente para paneles, barra lateral y botones.
- Aplicación en vivo con actualización agrupada.
- Caché del fondo escalado para evitar trabajo repetido.

## Compatibilidad

- `CONFIG_VERSION` continúa en 2.0.0.
- `.Nika` continúa en versión 1.
- Perfiles y mapas avanzados anteriores siguen funcionando.
- No se modifica la ruta HID, ViGEm, giroscopio, macros ni Input Studio.
