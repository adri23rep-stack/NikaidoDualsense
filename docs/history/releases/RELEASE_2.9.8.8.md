# Nikaido DualSense 2.9.8.8 Beta 1 — Dashboard Startup Fallback Hotfix

## Problema corregido

Al reconstruir el Dashboard, un perfil sin icono personalizado podía entrar en la ruta de respaldo visual. `dashboard.py` llamaba a `fallback_glyph(...)`, pero no importaba esa función. El resultado era un `NameError` durante el inicio gráfico y la aplicación caía al modo consola.

El fallo podía parecer intermitente porque un primer arranque podía encontrar una imagen válida o conservar una vista ya construida, mientras que un arranque posterior reconstruía el icono mediante el fallback.

## Solución

- `DashboardPage` importa `fallback_glyph` directamente desde `gui.profile_visuals`, módulo responsable de la identidad visual de perfiles.
- Se mantiene la prioridad actual:
  1. `icon_path` personalizado.
  2. `image_path` legado.
  3. Icono textual explícito.
  4. Glyph temático seguro.
- Una ruta de imagen inexistente ya no impide representar el perfil.
- No se cambió el formato de configuración ni la migración de iconos y banners.

## Regresión automática

La prueba nueva verifica con PySide6:

- Dos actualizaciones consecutivas del Dashboard sin icono personalizado.
- Perfil con identificador visual `theme:*`.
- Ruta personalizada inexistente.
- Resolución final mediante `fallback_glyph` sin excepción.

## Compatibilidad

- Perfiles y configuraciones de 2.9.8.7 se conservan.
- Iconos, banners y paquetes `.Nika` no cambian de formato.
- El Estilo A de selección permanece intacto.

## Límites honestos

- No se realizó prueba física con un DualSense.
- No se ejecutó Nuitka ni Inno Setup sobre Windows.
