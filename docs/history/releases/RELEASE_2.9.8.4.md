# Nikaido DualSense 2.9.8.4 Beta 1 — Game Profile Gallery

## Motivo

Profile Studio Lite corrigió el consumo excesivo, pero su presentación todavía no representaba la dirección visual aprobada. Esta versión reconstruye la sección como una galería moderna sin recuperar las animaciones continuas que causaron lentitud.

## Interfaz

- Nueva galería de perfiles basada en la opción visual aprobada.
- Vista de cuadrícula y vista compacta.
- Búsqueda con espera breve, filtros por categoría y origen, orden recomendado, alfabético, por categoría o favoritos.
- Panel lateral con una portada grande y cinco accesos claros:
  - RGB Studio
  - Gatillos adaptativos
  - Vibración
  - Macros
  - Input Studio
- Seleccionar un perfil no lo aplica automáticamente.
- Doble clic o el botón **Aplicar** cambia el perfil activo.
- Edición, duplicado, exportación, favoritos, restauración y eliminación contextual.
- Diseño responsive: el detalle pasa debajo de la galería cuando el ancho disponible es reducido.

## Ocho perfiles incluidos

1. Call of Duty: Warzone
2. Forza Horizon 5
3. Resident Evil 4
4. Elden Ring
5. EA Sports FC
6. Street Fighter 6
7. Minecraft
8. Ghost of Tsushima

Cada uno tiene configuración propia de L2/R2, vibración, RGB e Input Studio. Se construyen desde el mismo catálogo y los mismos presets que utiliza Trigger Studio.

## Arte y atribución

- Las portadas son arte geométrico original de Team Nikaido.
- No se incluyen logotipos, portadas, capturas ni archivos de terceros.
- Los perfiles son comunitarios no oficiales y la interfaz muestra una nota de no afiliación.
- Consulta `docs/UNOFFICIAL_GAME_PROFILES.md`.

## Arquitectura

- `src/profile_catalog.py`: catálogo, presentación, aliases y reglas de migración.
- `src/trigger_engine.py`: construcción física de los perfiles desde presets validados.
- `gui/profile_gallery.py`: portadas, tarjetas y panel lateral estáticos.
- `gui/profile_editor.py`: editor completo separado de la página.
- `gui/pages/profiles.py`: búsqueda, filtros, selección y operaciones.
- `tools/generate_profile_library_assets.py`: generador local y reproducible del arte original.

## Compatibilidad y migración

- Se conservan IDs históricos para evitar romper reglas automáticas, macros, favoritos y paquetes `.Nika`.
- `sniper` y `smg` permanecen como aliases compatibles, pero no crean tarjetas duplicadas.
- La migración restaura la nueva identidad, gatillos, RGB y vibración de perfiles incluidos.
- Se preservan imágenes personales, Input Studio, mapeo avanzado y audio.
- Los perfiles personalizados se conservan completos.
- Al crear o duplicar un perfil incluido, su portada original se copia a un archivo personal estable.
- La configuración anterior se respalda antes de persistir la migración.

## Rendimiento

- Sin `QTimer` dentro de las tarjetas ni del panel de galería.
- Sin previews RGB animados por perfil.
- Portadas con caché limitada.
- Búsqueda agrupada a 180 ms.
- Resize agrupado a 120 ms.
- Selección parcial: solo cambian las tarjetas involucradas y el panel de detalle.
- Los elementos internos de cada acceso del panel son transparentes al mouse para conservar clics confiables.
- El timer de preview del editor se detiene siempre al aceptar, cancelar o cerrar el diálogo.
- Los diálogos terminados se liberan con `deleteLater()` y las operaciones fallidas limpian imágenes e Input Studio.

## Seguridad

- Metadatos, tags, rutas, colores, Input Studio y mapeos cargados desde overrides se sanitizan.
- IDs reservados no pueden ser reemplazados por perfiles importados o personalizados.
- El generador de portadas no realiza descargas ni conexiones de red.

## Límites

- No se realizó prueba física con un DualSense en este entorno.
- No se compiló el instalador en Windows.
- Las dos pruebas que requieren PySide6 se omiten cuando esa dependencia no está instalada.
- La apariencia final debe revisarse en Windows con escalas de 100 %, 125 % y 150 %.
