# Revisión técnica — Nikaido DualSense 2.0

## Objetivo

Preparar Nikaido DualSense como una versión 2.0 más estable, coherente y fácil de mantener, conservando las funciones y datos existentes. No se añadieron módulos ajenos al alcance; el trabajo se concentró en interfaz, experiencia de uso, rendimiento, persistencia y arquitectura.

## Cambios principales

### Interfaz y experiencia de uso

- Se creó un sistema visual compartido en `gui/design_system.py` para colores, tarjetas, botones, estados, tooltips y avisos.
- La barra lateral ahora está agrupada y tiene desplazamiento, por lo que no se corta en ventanas pequeñas.
- Los perfiles usan una cuadrícula adaptable y evitan reconstruir tarjetas cuando su contenido no cambió.
- La mayoría de los avisos informativos dejaron de bloquear la interfaz; las confirmaciones destructivas siguen siendo modales.
- Se añadieron transiciones controladas entre páginas y se corrigieron efectos que podían quedar pegados al navegar rápido.
- Se restauran y guardan tamaño y posición de la ventana sin escribir al disco en cada pixel de movimiento.

### Rendimiento y estabilidad

- Los cambios continuos de sliders y editores se agrupan antes de guardarse, manteniendo la vista previa inmediata sin castigar el disco.
- La telemetría y las vistas en vivo solo actualizan la página visible.
- La configuración se escribe de forma atómica y conserva respaldos rotativos.
- Un archivo de configuración dañado puede recuperarse desde el respaldo válido más reciente.
- Los logs ahora rotan para evitar crecimiento indefinido.
- El apagado detiene cada servicio de manera independiente; un fallo en un módulo no impide cerrar los demás.
- Las acciones de la bandeja pasan por señales seguras de Qt en lugar de modificar la interfaz desde otro hilo.
- Los callbacks defectuosos de alta frecuencia se desconectan para evitar tormentas de errores y consumo innecesario.

### Calibración e Input Studio

- La calibración quedó organizada como asistente de cuatro pasos: stick izquierdo, stick derecho, giroscopio y gatillos.
- Incluye progreso, datos en vivo, validación, guardado automático y restauración de valores del perfil activo.
- Gyro Studio e Input Studio persisten los cambios con guardado agrupado y mantienen la respuesta inmediata del motor.
- Se conservaron curvas, puntos arrastrables, grid, presets, zoom, configuración por perfil y vista previa ya existentes.

### Macros, luces y gatillos

- La búsqueda de macros está agrupada para evitar reconstruir la biblioteca en cada tecla.
- El editor, grabación, timeline, copiar/pegar, duplicar y agrupar existentes se conservaron.
- Luces, vibración y gatillos mantienen vista previa en vivo mientras el guardado del perfil se realiza de forma agrupada.
- Las animaciones RGB importadas ya no sobrescriben otra animación con el mismo identificador.

### Perfiles `.Nika`

- `.Nika` queda centralizado como formato oficial de intercambio de perfiles.
- La exportación es atómica e incluye los datos relacionados ya soportados por el proyecto.
- La importación valida versión, tamaño total, tamaño por archivo y cantidad de elementos.
- Se mantienen compatibles los perfiles JSON anteriores.
- Las imágenes demasiado grandes se rechazan antes de cargarlas en la interfaz.

### Arquitectura

- La interfaz activa continúa en `gui/modern_app.py`, pero sus componentes visuales compartidos se movieron a `gui/design_system.py`.
- La antigua interfaz CustomTkinter se movió a `legacy/customtkinter_app.py`; ya no forma parte del arranque ni del paquete final.
- `gui/app.py` conserva imports antiguos y redirige a la interfaz Qt actual.
- La versión de aplicación, configuración y paquete se centralizó en `nikaido_version.py`.
- La configuración de pruebas se dejó en `pytest.ini` para que las pruebas arranquen sin ajustar manualmente `PYTHONPATH`.

## Compatibilidad

Se conservaron las estructuras existentes de perfiles, macros, Input Studio, giroscopio, luces y configuración. Las migraciones agregan valores faltantes sin borrar campos desconocidos. La importación JSON anterior permanece disponible y el formato `.Nika` añade validación sin cambiar los datos internos que ya usa el programa.

## Validación realizada

- Suite principal con **89 pruebas aprobadas**.
- Suite adicional de temas e interfaces personalizadas con **10 pruebas aprobadas**.
- Compilación sintáctica de todos los módulos mediante `compileall`.
- Pruebas específicas de recuperación de configuración, paquetes `.Nika`, watcher de juegos, bandeja, cierre seguro, navegación, calibración y pulido de interfaz.

## Límite de esta revisión

El entorno de revisión no incluye Windows, PySide6 ni un DualSense físico. Por ello no fue posible ejecutar una inspección visual real de la ventana, generar el `.exe` de Windows ni validar USB/Bluetooth, audio, ViGEm y gatillos sobre hardware. Esas comprobaciones deben hacerse en Windows antes de publicar una build firmada.

## Recomendación para la siguiente etapa

Antes de seguir agregando funciones, conviene crear capturas de referencia y pruebas visuales de cada página en Windows. Con esa red de seguridad podrá dividirse gradualmente `gui/modern_app.py` en módulos por página sin arriesgar regresiones visuales o conexiones rotas.
