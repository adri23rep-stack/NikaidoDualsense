# Nikaido DualSense 2.9.8.3 Beta 1 — Profile Studio Lite

## Motivo
La versión anterior abrió correctamente la pestaña Perfiles, pero el diseño quedó recargado y el repintado continuo hacía que la pantalla se sintiera lenta. Esta revisión prioriza claridad, respuesta inmediata y bajo consumo.

## Interfaz
- Conserva la vista híbrida: galería de tarjetas y panel lateral.
- Reduce la altura y cantidad de elementos dentro de cada tarjeta.
- Elimina chips repetidos, estadísticas decorativas y acciones secundarias de la galería.
- Las tarjetas muestran nombre, categoría, descripción corta, L2, R2 e iluminación.
- Aplicar y Editar permanecen visibles; Clonar, favoritos, estudios y eliminar viven en el panel lateral.
- Los avatares usan un diseño plano con una franja de identidad, sin halos ni arcos giratorios.
- Las imágenes personalizadas continúan teniendo prioridad.

## Rendimiento
- El reloj de animación de la galería ya no se inicia.
- Se elimina un `NeonEffectIcon` animado por cada tarjeta.
- Seleccionar un perfil actualiza únicamente la tarjeta anterior, la nueva y el panel lateral.
- La búsqueda usa una espera de 170 ms para evitar reconstruir con cada tecla.
- El resize se agrupa y solo reconstruye cuando cambia la cantidad de columnas o el modo compacto.
- El preview del editor baja de 20 FPS a aproximadamente 5.5 FPS.

## Compatibilidad
- Conserva perfiles, IDs históricos, favoritos, imágenes, reglas automáticas y paquetes `.Nika`.
- No cambia el formato de configuración.
- Mantiene los perfiles de fábrica y presets añadidos en 2.9.8.1.

## Límites
- No se realizó prueba física con un DualSense.
- No se compiló el instalador en Windows en este entorno.
- Las pruebas GUI que requieren PySide6 permanecen omitidas cuando la dependencia no está disponible.
