# Reporte técnico — Nikaido DualSense 2.3.2

## Objetivo

Cerrar la etapa de pulido con una bandeja del sistema útil y confiable. Al minimizar, Nikaido permanece junto al reloj de Windows y el icono informa el estado real del DualSense sin abrir la ventana.

## Implementación

### Icono dinámico de batería

Se reconstruyó `src/system_tray.py` para representar:

- logo oficial de Nikaido;
- conexión o desconexión;
- nivel de batería mediante relleno visual;
- color verde, amarillo o rojo según el porcentaje;
- carga mediante color cian y rayo;
- estado neutral mientras llega el primer informe de batería;
- desconexión mediante icono atenuado y marca roja.

El porcentaje exacto se mantiene en tooltip y menú porque un número sería ilegible cuando Windows reduce el icono a 16×16.

### Interacción con la bandeja

- Clic izquierdo o activación principal: restaurar Nikaido.
- Clic derecho: abrir menú rápido.
- Estado de conexión visible.
- Porcentaje y carga visibles.
- Perfil activo visible.
- Cambio de perfil sin abrir la ventana.
- Salida completa desde la bandeja.
- Notificación explicativa una sola vez por sesión al minimizar.

### Sincronización

Conexión, batería y perfil pueden actualizarse desde hilos distintos. El gestor ahora usa un bloqueo interno para proteger:

- referencias al icono y su hilo;
- estado de conexión;
- batería y carga;
- perfil activo;
- caché del render;
- inicio y cierre.

Si el backend de pystray termina inesperadamente, el estado interno deja de afirmar que la bandeja sigue disponible. Así Nikaido nunca se oculta sin una forma de recuperarlo.

### Rendimiento

- Caché por estado de batería, carga y conexión.
- Máximo de 64 imágenes para impedir crecimiento indefinido.
- No se vuelve a renderizar si el estado visual no cambió.
- Menú solo se reconstruye cuando cambia información relevante.
- Callbacks duplicados no se registran dos veces.

### Empaquetado de Windows

El compilador ahora incluye explícitamente:

- `pystray` completo;
- backend `pystray._win32`;
- `PIL.Image` y `PIL.ImageDraw`;
- renderizador de bandeja.

El auto-test del EXE comprueba antes de generar el ZIP:

- backend HID;
- importación de pydualsense;
- enumeración HID;
- importación del backend de bandeja de Windows;
- render correcto del icono dinámico.

Una compilación sin bandeja funcional ya no puede marcarse como válida.

## Comportamiento de cierre

- Minimizar (`−`) usa la bandeja cuando la opción está activa.
- Cerrar (`×`) sigue terminando Nikaido por completo.
- Salir desde el menú de bandeja también finaliza motores, icono y proceso.
- Sin bandeja disponible, minimizar usa la barra de tareas normal.

## Compatibilidad

No se modificaron:

- HID y lectura del DualSense;
- ViGEm;
- giroscopio;
- Input Studio;
- macros;
- perfiles `.Nika`;
- `CONFIG_VERSION`;
- `NIKA_FORMAT_VERSION`.

## Validación

- **183 pruebas automatizadas aprobadas**.
- Todos los módulos compilan con `compileall`.
- No existen métodos duplicados dentro de clases.
- Iconos revisados a 96×96 y a tamaño real de bandeja 16×16.
- ZIP validado después del empaquetado.

## Versión

- `APP_VERSION`: `2.3.2`
- `CONFIG_VERSION`: `2.0.0`
- `NIKA_FORMAT_VERSION`: `1`

## Nota de Windows

Nikaido crea correctamente el icono en el área de notificación. Windows decide si lo muestra directamente junto al reloj o dentro del menú `^` de iconos ocultos. El usuario puede arrastrarlo hacia afuera o fijarlo desde la configuración de la barra de tareas.
