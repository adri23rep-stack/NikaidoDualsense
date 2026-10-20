# Nikaido DualSense 2.9.8.5 Beta 1 — Profile Gallery Startup Hotfix

## Motivo

La separación de Profile Gallery movió `ProfileEditorDialog` y `profile_image_widget` a `gui/profile_editor.py`, pero el facade público `gui/modern_app.py` todavía intentaba obtener ambos símbolos desde `gui/pages/profiles.py`. En Windows, el import de la interfaz fallaba antes de abrir la aplicación:

```text
ImportError: cannot import name 'profile_image_widget' from 'gui.pages.profiles'
```

El script de inicio mezclaba en una sola comprobación las dependencias externas y el código de Nikaido. Por eso interpretaba el error del proyecto como un runtime incompleto y reinstalaba `comtypes`, `pycaw`, `psutil` y las demás dependencias sin poder corregir la causa real.

## Corrección de arquitectura

- `gui/modern_app.py` ahora importa:
  - `ProfileEditorDialog` y `profile_image_widget` desde `gui/profile_editor.py`.
  - `ProfilesPage` desde `gui/pages/profiles.py`.
- `gui/pages/profiles.py` conserva un re-export explícito de compatibilidad para plugins o código histórico que todavía use esa ruta.
- Se añadió un `__all__` pequeño y explícito para los tres símbolos públicos relacionados con perfiles.

## Inicio e instalación

- `INICIAR_NIKAIDO.bat` separa cuatro etapas:
  1. Python del runtime.
  2. Dependencias GUI/audio.
  3. Código de Nikaido.
  4. Inicio de la aplicación.
- Solo se reinstalan paquetes cuando falla la comprobación de dependencias.
- Si las dependencias están disponibles pero el código no puede importarse, el launcher muestra un error de proyecto y no modifica el runtime.
- `install.bat` aplica la misma separación durante una instalación nueva o reparación.
- Un fallo de importación del proyecto devuelve código de salida `2`, distinto al fallo de dependencias.

## Pruebas de regresión

Se añadió `tests/test_hotfix_2985_profile_gallery_startup.py` para comprobar:

- Que el facade importa cada símbolo desde su módulo dueño.
- Que `profile_editor.py` realmente exporta `ProfileEditorDialog` y `profile_image_widget`.
- Que la ruta histórica `gui.pages.profiles` sigue siendo compatible.
- Que el launcher no reinstala dependencias por un error del código.
- Que el instalador separa validación de paquetes y validación del proyecto.

## Compatibilidad

- No modifica perfiles, favoritos, macros, RGB, gatillos, Input Studio ni reglas por juego.
- No requiere borrar el runtime corto existente.
- Conserva la Game Profile Gallery y los ocho perfiles incluidos de 2.9.8.4.
- Conserva compatibilidad con imports históricos de la interfaz modular.

## Límites

- No se realizó prueba física con un DualSense.
- PySide6 no está instalado en el entorno Linux de revisión, por lo que el smoke test Qt real fue omitido.
- No se compiló Nuitka ni el instalador de Windows en este entorno.
- El error exacto fue reproducido por el registro de Windows proporcionado y cubierto mediante validación estática del facade y suite completa.
