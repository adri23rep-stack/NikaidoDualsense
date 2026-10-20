# Nikaido DualSense 2.9.8.6 Beta 1 — Profile Editor Actions Hotfix

## Motivo

La galería de perfiles abría correctamente, pero los botones **Editar perfil** y **Nuevo perfil** parecían no hacer nada.

La causa de edición estaba dentro de `gui/profile_editor.py`: el diálogo usaba el helper visual `label(...)` al construir la pestaña **Perfil completo**, pero ese helper no estaba importado. Qt ejecutaba el callback del botón, la construcción del diálogo fallaba con `NameError` y la excepción quedaba dentro del flujo de eventos, por eso la interfaz no mostraba una explicación visible.

Crear un perfil tenía un segundo problema independiente: dependía exclusivamente de `TriggerEngine.get_current_profile()`. Antes de conectar el DualSense o aplicar un perfil, ese valor puede ser `None`, así que la acción regresaba sin abrir el editor.

## Correcciones

### Editor de perfiles

- `gui/profile_editor.py` importa ahora todos los helpers que utiliza durante la construcción del diálogo.
- Se verificó la construcción completa de las cuatro pestañas:
  - General.
  - L2.
  - R2.
  - Perfil completo.
- Se validó el guardado del nombre, categoría, descripción, etiquetas, icono, vibración, gatillos y configuración RGB.
- El temporizador de vista previa sigue deteniéndose al cerrar el diálogo.

### Nuevo perfil

- La fuente inicial se resuelve en este orden:
  1. Perfil actualmente aplicado.
  2. Perfil seleccionado en la galería.
  3. Perfil base oficial de Nikaido.
  4. Primer perfil disponible como último respaldo.
- La creación funciona aunque el control aún no esté conectado o no exista un perfil aplicado.
- Si no existe ningún perfil base disponible, se muestra un error claro en vez de ignorar el clic.
- Se conserva la copia segura de imagen, Input Studio y demás configuración del perfil base.

## Pruebas Qt reales

Se añadió `tests/test_hotfix_2986_profile_editor_actions.py` y se ejecutó con PySide6 6.8.3 usando la plataforma `offscreen`.

La prueba cubre:

- Construcción y guardado del editor para los ocho perfiles incluidos.
- Clic real en **Nuevo perfil** sin perfil activo.
- Creación y persistencia de un perfil personalizado.
- Clic real en **Editar perfil** desde el panel lateral.
- Actualización y persistencia del perfil editado.
- Confirmaciones `Perfil creado` y `Perfil guardado`.

## Compatibilidad

- Conserva los ocho perfiles de juegos de 2.9.8.4.
- Conserva el hotfix de arranque de 2.9.8.5.
- No cambia el formato `.Nika`, la estructura de `profiles.json` ni los IDs históricos.
- No elimina perfiles, favoritos, macros, reglas por juego, imágenes o configuraciones existentes.

## Límites

- No se realizó prueba física con un DualSense.
- No se compiló Nuitka ni el instalador de Windows en este entorno.
- La interfaz sí fue ejecutada mediante Qt/PySide6 en modo `offscreen`, pero no se validó visualmente en un escritorio Windows real.
