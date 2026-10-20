# Nikaido DualSense 2.7.0

## Nikaido llega al programa

Esta versión integra por primera vez a la mascota oficial dentro del wizard de bienvenida.

### Wizard renovado

- Panel lateral permanente con sprite de cuerpo completo.
- Seis escenas: bienvenida, conexión, perfiles, herramientas, apariencia y cierre.
- Diálogo contextual y pose diferente en cada paso.
- Estado real del DualSense con conexión USB/Bluetooth y batería.
- Botón **Buscar ahora** para iniciar la detección desde el propio asistente.
- Reacción feliz cuando el control aparece.
- Tamaño y distribución ajustados para conservar espacio útil en las opciones.

### Base reutilizable

- Nuevo componente `MascotPanel` dentro de `gui/components.py`.
- 10 sprites de cuerpo completo y 10 sprites compactos preparados para usos futuros.
- Rutas normalizadas sin acentos para evitar problemas de empaquetado.
- Recursos incluidos automáticamente dentro de `assets`, tanto en desarrollo como en PyInstaller.

### Compatibilidad

- El onboarding sube a la versión 3, por lo que el recorrido renovado puede mostrarse a instalaciones existentes.
- No se modificaron perfiles `.Nika`, macros, emulación, gyro ni rutas de configuración.
- El wizard continúa pudiendo abrirse manualmente desde Ajustes.
