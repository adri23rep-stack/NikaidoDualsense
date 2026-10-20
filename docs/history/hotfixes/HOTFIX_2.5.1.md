# Nikaido DualSense 2.5.1 — Hotfix Wizard y Nexus

## Correcciones

- Corregido el cierre inesperado al entrar a la página 5 (Apariencia) del asistente.
  La vista previa utilizaba una fuente local sin inicializar cuando el logo SVG sí estaba disponible.
- Corregido **Guardar acción** en Nikaido Nexus.
  El editor intentaba usar un mensaje de validación que no había sido creado.
- Los cuatro controles de tiempo de Nexus permanecen editables en todos los gestos.
  Una ayuda contextual indica qué valores usa el gesto seleccionado.
- Añadidas pruebas de interfaz reales para pintar la vista previa, recorrer el wizard y guardar/editar acciones.

## Alcance

Este hotfix no modifica emulación, gyro, perfiles automáticos, HidHide ni feedback de vibración.
