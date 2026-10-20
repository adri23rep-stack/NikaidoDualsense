# Validación Nikaido DualSense 2.9.8.7 Beta 1

## Automatización

- `pytest -q` con PySide6 6.8.3 y `QT_QPA_PLATFORM=offscreen`.
- Resultado: **497 pruebas aprobadas, 0 fallos, 0 omitidas**.
- Compilación sintáctica de **161 archivos Python**: 0 errores.
- Importación de arranque verificada para:
  - `gui.modern_app`
  - `gui.profile_editor`
  - `gui.pages.profiles`
  - `gui.profile_gallery`

## Pruebas Qt reales

- Construcción del editor para los ocho perfiles incluidos.
- Guardado del editor.
- Creación de perfil sin DualSense conectado.
- Edición desde el panel lateral.
- Creación con icono y banner personalizados.
- Eliminación solamente del icono manteniendo intacto el banner.
- Verificación de sombra desactivada en tarjetas normales y activa en la seleccionada.
- Render offscreen de la galería y el editor para revisión visual.

## Datos y paquetes

- Roundtrip de `WeaponProfile` con `icon_path` y `banner_path`.
- Exportación `.Nika` con icono y banner.
- Importación del mismo paquete conservando archivos independientes.
- Migración de paquete antiguo con una sola imagen a icono y banner separados.
- Compatibilidad JSON 2.0 mantenida.

## Límites

- No hubo hardware DualSense disponible.
- No se ejecutó Nuitka ni Inno Setup sobre Windows.
