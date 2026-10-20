# Cambios de Nikaido UI Studio

## Integración terminada

- Renderer de temas dentro de la ventana principal.
- Aplicación en vivo desde el editor.
- Carga automática al iniciar y alternancia con `F12`.
- Pantallas internas con navegación e historial.
- Acciones conectadas con perfiles, gatillos, botones, macros, emulación, LED, Bluetooth y ventana.
- Datos dinámicos de conexión, batería, perfil, emulación, macros, gatillos, fecha y hora.
- Elementos: imagen/GIF, texto, globo, botón, barra dinámica, rectángulo, elipse y zona invisible.
- Estados hover y presionado, incluyendo imágenes alternativas.
- Condiciones de visibilidad.
- Capas, rejilla, ajuste, zoom, bloqueo, rotación, opacidad y redimensionado.
- Deshacer/rehacer, copiar/pegar, duplicar y autoguardado de recuperación.
- JSON local y paquetes `.nikaido-theme` portables.
- Migración de diseños antiguos al esquema 3.
- Validación y extracción segura de paquetes.
- Plantilla inicial de tres pantallas lista para modificar.
- Pruebas automáticas de formato, migración, seguridad y portabilidad.

## Límite de prueba

El editor, renderer, navegación, paquetes y arranque de la aplicación se probaron sin hardware. Las acciones que envían datos físicos al DualSense siguen dependiendo de un control real, sus drivers y el backend ya existente del proyecto.

## Corrección de propiedades y aplicación en vivo

- Las propiedades del elemento ahora se reflejan automáticamente en el lienzo.
- La lectura de propiedades es atómica: un campo inválido ya no deja cambios parciales.
- Los cambios pendientes se conservan al seleccionar otra capa.
- **Aplicar y ver en Nikaido** guarda una copia de trabajo automáticamente, incluso si el diseño aún no se guardó manualmente.
- Al aplicar, el editor se oculta y la ventana principal pasa al frente para mostrar el resultado real.
- El renderer recibe una instantánea independiente del diseño para evitar modificaciones a medias.
