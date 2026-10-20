# Reporte de Nikaido DualSense 2.5.1

## Motivo del hotfix

Durante la primera prueba real de la versión 2.5.0 se detectaron tres problemas de interfaz:

1. El asistente se cerraba al avanzar a la página 5, Apariencia.
2. Nikaido Nexus no aceptaba el botón **Guardar acción**.
3. Los controles de tiempo parecían bloqueados según el gesto seleccionado.

## Causas encontradas

### Crash del asistente

`AppearancePreview.paintEvent()` creaba la variable de fuente únicamente dentro del caso alternativo usado cuando el logo SVG no cargaba. En una instalación normal el logo sí cargaba y la variable se utilizaba sin existir al pintar la página de Apariencia.

### Guardado de acciones

`AdvancedBindingDialog.accept()` mostraba u ocultaba `self.validation`, pero el diálogo nunca construía ese control. Esto producía un error al guardar incluso una acción válida.

### Tiempos bloqueados

El editor desactivaba físicamente cada control cuando el gesto actual no lo utilizaba. Los valores sí formaban parte de la acción, pero la interfaz impedía prepararlos o modificarlos con libertad.

## Correcciones aplicadas

- La fuente de la vista previa se inicializa antes de revisar el logo.
- El editor de acciones crea su mensaje de validación antes de los botones.
- Los cuatro valores de tiempo permanecen editables:
  - umbral de pulsación larga;
  - ventana de doble pulsación;
  - duración del pulso de salida;
  - velocidad de turbo.
- Se añadió una explicación contextual que indica qué tiempos utiliza el gesto actual.
- La versión se actualizó a 2.5.1 en aplicación, paquete e instalador.

## Validación

- `python -m compileall -q .`: aprobado.
- Suite completa: **211 pruebas aprobadas**.
- Auto-prueba 2.5: aprobada.
- No se modificaron los motores HID, gyro, emulación, feedback virtual, perfiles automáticos ni HidHide.

## Validación pendiente en Windows

Este entorno de revisión no incluye PySide6, por lo que la apertura visual final debe confirmarse en Windows. Las correcciones atacan directamente las líneas que causaban ambos errores reportados.
