# Nikaido DualSense 2.9.8.7 Beta 1 — Profile Visual Identity

## Objetivo

Pulir la selección de tarjetas de Profile Studio y separar correctamente la identidad visual de cada perfil en dos recursos independientes: icono y banner.

## Estilo A · Sobrio premium

- La tarjeta seleccionada ya no cambia a un borde morado, cian o verde.
- Todas las tarjetas conservan el mismo borde fino del tema.
- La selección usa un fondo ligeramente más claro y una sombra suave.
- El hover usa una sombra menor y no modifica el borde.
- El perfil aplicado se identifica únicamente con el badge `ACTIVO`.
- Los efectos gráficos permanecen desactivados en tarjetas normales; solo se habilitan para la seleccionada o la que está bajo el mouse.
- No se añadieron animaciones continuas, temporizadores por tarjeta ni reconstrucciones adicionales.

## Icono y banner independientes

Cada `WeaponProfile` ahora conserva:

- `icon`: tema vectorial o identificador visual.
- `icon_path`: imagen cuadrada personalizada.
- `banner_path`: portada horizontal personalizada.
- `image_path`: alias legado de `icon_path` para compatibilidad.

El editor permite:

- Elegir un icono personalizado.
- Volver al icono vectorial predeterminado.
- Elegir un banner horizontal.
- Restaurar el banner incluido por Team Nikaido.
- Previsualizar ambos recursos sin escribirlos al disco hasta guardar.

## Persistencia y compatibilidad

- Iconos se optimizan en `profile_images` para conservar rutas anteriores.
- Banners se guardan en `profile_banners`.
- Editar o eliminar un icono ya no modifica el banner.
- Si un perfil antiguo comparte un solo archivo, Nikaido copia primero el banner a su propio archivo antes de cambiar el icono.
- Duplicar un perfil crea copias independientes de ambos recursos.
- Eliminar o restaurar limpia ambos archivos.
- Dashboard usa el icono y Profile Gallery usa el banner.

## Formato `.Nika`

Los paquetes nuevos pueden incluir:

- `assets/profile.*` como icono compatible con versiones anteriores.
- `assets/banner.*` como portada.
- `icon_file` y `banner_file` en el manifiesto.
- `image_file` se conserva apuntando al icono para lectores anteriores.

Los paquetes antiguos que contienen una sola imagen se importan creando dos archivos físicos separados. De esa forma una edición futura no acopla icono y portada.

## Pruebas

- Modelo y serialización de icono/banner.
- Migración de `image_path` legado.
- Exportación e importación `.Nika` con ambos recursos.
- Importación de paquetes antiguos de una sola imagen.
- Creación real de perfiles con icono y banner mediante Qt offscreen.
- Edición para quitar únicamente el icono preservando el banner.
- Estado de sombra seleccionado/normal.
- Suite completa del proyecto.

## Límites honestos

- No se realizó prueba física con un DualSense.
- No se compiló el instalador en Windows dentro de este entorno.
- Las pruebas visuales se realizaron con PySide6 6.8.3 usando el backend Qt `offscreen`.
