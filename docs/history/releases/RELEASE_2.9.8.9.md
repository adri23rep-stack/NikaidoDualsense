# Nikaido DualSense 2.9.8.9 Beta 1 — Stability & Lifecycle Audit

## Alcance

Esta versión es una copia separada de 2.9.8.8. Prioriza estabilidad y
mantenibilidad en el arranque, el ciclo de vida de PySide6, Profile Studio,
la persistencia y el diagnóstico del launcher. No añade funciones de producto
ni modifica el diseño visual.

## Causas verificadas antes de modificar

- Cada `NikaidoWindow` registraba lambdas en `ConnectionManager` y
  `TriggerEngine` sin una operación de baja. Después de tres ciclos quedaban
  tres ventanas Python vivas, 30 widgets Qt de nivel superior y callbacks
  acumulados en todos los canales observados.
- Varios `QTimer.singleShot` conservaban métodos ligados a la ventana fuera de
  un dueño Qt cancelable. `BackendBridge` y `MouseCaptureOverlay` tampoco tenían
  un padre de ciclo de vida explícito.
- Los callbacks de perfil y gatillos ocultaban sus excepciones. Las acciones de
  Profile Studio no compartían una frontera de error, por lo que un slot podía
  parecer un botón que no respondía.
- Un fallo de GUI en modo no interactivo se registraba y apagaba, pero no se
  propagaba; el proceso podía terminar con código 0 y el launcher lo interpretaba
  como éxito.
- El guardado de cierre estaba dentro de un solo `try`: el primer exportador
  defectuoso impedía guardar todos los subsistemas siguientes.
- La importación opcional de `pystray` solo toleraba `ImportError`; un backend
  instalado pero inutilizable podía romper la importación del núcleo.
- Una carpeta de logs o reportes no escribible podía abortar el arranque antes
  de que la interfaz mostrara un diagnóstico.
- Los BAT de reparación mezclaban dependencias y código del proyecto en una
  sola comprobación, lo que podía recomendar reinstalar paquetes ante un fallo
  del código.

## Correcciones

- Suscripciones con bajas idempotentes en conexión, gatillos y bandeja.
- Timers diferidos hijos de la ventana, cancelables y con registro de errores.
- Limpieza idempotente de timers, animaciones, diálogos, overlays, señales y
  objetos Qt; la ventana se elimina mediante `deleteLater`.
- Frontera de excepción para seleccionar, crear, editar, duplicar, aplicar,
  restaurar, eliminar, importar y exportar perfiles.
- Guardado aislado por subsistema y `save_config` independiente.
- Fallos no interactivos de GUI propagados al punto de entrada para devolver
  código de error.
- Bandeja opcional degradable con diagnóstico; logs y crash hooks con fallback.
- Comprobador independiente de dependencias usado por inicio, instalación y
  reparación antes de importar el código de Nikaido.

## Compatibilidad

- `CONFIG_VERSION` permanece en `2.0.0`.
- `NIKA_FORMAT_VERSION` permanece en `1`.
- Se conservan los ocho IDs incluidos y los aliases históricos.
- No cambian los esquemas de perfiles, configuraciones, iconos, banners ni
  paquetes `.Nika`.
- No se eliminó, desactivó ni simplificó ninguna función existente. La bandeja
  ya era opcional; ahora su degradación cubre también fallos del backend.

## Límites honestos

- No se usó un DualSense físico.
- No se ejecutó el programa en Windows.
- No se compiló con Nuitka ni se ejecutó Inno Setup.
- PySide6 se validó en Linux con `QT_QPA_PLATFORM=offscreen`.

© Team Nikaido
