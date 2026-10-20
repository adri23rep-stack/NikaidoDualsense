# Auditoría de seguridad — Nikaido DualSense 2.5.6

**Fecha:** 12 de julio de 2026  
**Base revisada:** Nikaido DualSense 2.5.5  
**Resultado:** versión endurecida 2.5.6  
**Alcance:** revisión estática, comparación de código, pruebas unitarias y
pruebas de entradas maliciosas simuladas.

> Esta revisión no sustituye una auditoría profesional con fuzzing de drivers,
> análisis del kernel, firma de binarios o pruebas físicas en Windows.

## Resumen

Se encontraron riesgos reales en importadores, consumo de recursos, búsqueda de
herramientas externas, reparación Bluetooth, privilegios del instalador y
privacidad de reportes. No se encontró ejecución de código desde perfiles o
temas, ni uso de `eval`, `exec`, `shell=True` o extracción ZIP con
`extractall`.

Todos los hallazgos de esta revisión fueron corregidos o reducidos de forma
conservadora. La suite pasó de 232 a **263 pruebas**.

## Hallazgos corregidos

### NIK-256-01 — Paquetes ZIP ambiguos o abusivos

**Severidad:** alta  
**Afectaba:** perfiles `.Nika` y temas `.nikaido-theme`.

La versión anterior comprobaba parte del tamaño y traversal, pero no cubría de
forma uniforme nombres ADS de NTFS, nombres reservados de Windows, duplicados
por mayúsculas/minúsculas, archivos cifrados, cantidad de miembros ni relación
de compresión. Un paquete especialmente preparado podía provocar escrituras
ambiguas, consumo excesivo de CPU/memoria o instalaciones incompletas.

**Parche aplicado:**

- Validador común de nombres ZIP.
- Bloqueo de rutas absolutas, `..`, barras invertidas, NUL, ADS y nombres
  reservados como `CON`, `AUX`, `NUL`, `COM1` o `LPT1`.
- Límites por miembro, paquete, cantidad, tamaño descomprimido y relación de
  compresión.
- Bloqueo de miembros cifrados y duplicados ambiguos.
- Extracción manual dentro de una carpeta contenida; no se usa `extractall`.

### NIK-256-02 — Lectura de recursos externos desde temas

**Severidad:** alta  
**Afectaba:** temas importados y sus imágenes.

Un manifest podía referenciar rutas absolutas o recursos fuera de la carpeta
del tema. Eso permitía que un tema no confiable intentara leer y copiar archivos
locales al volver a exportarse.

**Parche aplicado:** los temas empaquetados quedan encerrados en su propia
carpeta. Solo el editor local puede usar recursos externos de forma explícita.
También se rechazan rutas UNC, rutas de dispositivo y URL.

### NIK-256-03 — Suplantación de HidHide o gestores externos

**Severidad:** alta  
**Afectaba:** detección/ejecución de HidHide y su instalación.

La versión anterior podía aceptar `HidHideCLI.exe`, `HidHideClient.exe` o
`winget.exe` encontrados mediante `PATH`, además de una vista de registro que
podía incluir datos controlados por el usuario. Si Nikaido se ejecutaba elevado,
un ejecutable falso podía heredar esos permisos.

**Parche aplicado:**

- Se eliminó la búsqueda mediante `PATH`.
- Solo se lee HKLM y se aceptan rutas dentro de `Program Files`.
- Se comprueban nombres esperados antes de ejecutar el CLI/cliente.
- El botón de instalación abre directamente la publicación oficial de HidHide;
  no ejecuta un gestor encontrado en carpetas del usuario.
- Los IDs de dispositivo se validan antes de enviarse al CLI.

### NIK-256-04 — Reparación Bluetooth destructiva

**Severidad:** media-alta  
**Afectaba:** herramienta de reinicio Bluetooth.

La versión anterior eliminaba claves globales de emparejamiento bajo BTHPORT.
Esto podía desconectar audífonos, teclados, mouse y otros equipos que no tenían
relación con el DualSense.

**Parche aplicado:** la reparación ahora refresca únicamente dispositivos con
nombre DualSense/Wireless Controller y reinicia el servicio. Ya no borra claves
de emparejamiento. PowerShell se invoca por ruta del sistema, sin `PATH`, sin
perfil del usuario y usando únicamente scripts internos permitidos.

### NIK-256-05 — Denegación de servicio por JSON, macros o configuraciones

**Severidad:** media  
**Afectaba:** `.Nika`, macros, reglas por juego, Input Studio, luces, gatillos y
archivos de configuración.

Un archivo pequeño podía contener estructuras muy profundas, miles de acciones,
colecciones enormes o números no finitos. Esto podía congelar la interfaz,
consumir memoria o romper cálculos del control.

**Parche aplicado:**

- Tamaño máximo antes de leer archivos.
- Límites de profundidad, nodos, longitud de texto y elementos por colección.
- Rechazo de `NaN`, `Infinity` y `-Infinity`.
- Máximo de macros, pasos, reglas, perfiles, curvas y secciones personalizadas.
- Saneado y clamp de valores de gatillos, gyro, luces y Input Studio.

### NIK-256-06 — Imágenes y GIF diseñados para agotar memoria

**Severidad:** media  
**Afectaba:** imágenes de perfil, fondos y temas.

Validar únicamente el peso del archivo no evita imágenes con dimensiones
absurdas o animaciones con cientos de cuadros. Además, algunas rutas cargaban
la imagen directamente en Qt antes de comprobarla.

**Parche aplicado:**

- Verificación con Pillow antes de decodificar o mostrar.
- Límites de bytes, dimensiones, píxeles totales, cuadros y presupuesto de
  animación.
- Cachés de cuadros acotadas.
- Previsualización de imágenes de perfil desde datos ya validados, no mediante
  carga directa de un archivo no confiable en `QPixmap`.

### NIK-256-07 — Exposición innecesaria de rutas en logs y reportes

**Severidad:** media  
**Afectaba:** errores, crash reports y diagnóstico.

Excepciones podían guardar nombres de usuario, AppData, rutas privadas o
caracteres de control capaces de alterar visualmente un log.

**Parche aplicado:** sanitización centralizada de rutas de usuario, nombres y
caracteres de control. Los archivos locales sensibles reciben permisos de
usuario donde el sistema lo permite.

### NIK-256-08 — Privilegios e instalación global innecesarios

**Severidad:** media  
**Afectaba:** instalador y `install.bat`.

El instalador solicitaba administrador para una aplicación que no lo necesita
en uso normal, y el script podía modificar el Python global.

**Parche aplicado:** instalación por usuario en LocalAppData con
`PrivilegesRequired=lowest`. El script crea `.venv` y usa `python -m pip` dentro
de ese entorno. Los drivers conservan sus propios instaladores externos cuando
Windows requiera elevación.

### NIK-256-09 — Integridad insuficiente de la distribución

**Severidad:** baja-media  
**Afectaba:** verificación de paquetes compilados.

El manifiesto no permitía comprobar cada archivo individual de una distribución.

**Parche aplicado:** `MANIFEST.json` incluye ruta, tamaño y SHA-256 por archivo.
El compilador de Inno Setup tampoco se busca mediante un `PATH` no confiable.

### NIK-256-10 — Dependencias sin control continuo

**Severidad:** variable  
**Afectaba:** instalación y mantenimiento.

**Parche aplicado:** dependencias de ejecución, desarrollo y compilación fueron
separadas y acotadas. Pillow requiere 12.2.0 o posterior dentro de la rama 12.x.
El CI de Windows ejecuta `pip-audit` en cada cambio, además de pruebas, Ruff y
Bandit.

## Validación realizada

- `python -m compileall`: aprobado.
- `python -m pytest -q`: **263 aprobadas**.
- `SOURCE_MANIFEST.json`: todos los archivos fuente verificados por tamaño y SHA-256.
- Ruff crítico: aprobado.
- Bandit con severidad media/alta: **0 hallazgos**.
- Escaneo manual: sin `eval`, `exec`, `shell=True`, `os.system`, `pickle`,
  `yaml.load` ni `ZipFile.extractall` en el código de la aplicación.
- Pruebas específicas para traversal, ADS, nombres reservados, ZIP bomb, JSON
  profundo, números no finitos, macros gigantes, imágenes enormes, HidHide,
  Bluetooth, redacción y límites de motores.

## Validaciones pendientes en Windows

- Enumeración HID y comunicación física USB/Bluetooth.
- Feedback ViGEm hacia el DualSense.
- HidHide con el driver realmente instalado.
- Reinicio del servicio Bluetooth con elevación de Windows.
- Instalación y desinstalación mediante Inno Setup.
- Click-through y comportamiento de Qt en pantalla completa exclusiva.

La auto-prueba HID no pudo ejecutarse en el entorno Linux de revisión porque no
están instalados los backends HID/Win32. `pip-audit` tampoco pudo consultar PyPI
por falta de red; queda configurado en CI para ejecutarse en Windows con acceso
a Internet.

## Riesgos que permanecen

1. **Falta firma digital de binarios.** El SHA-256 detecta cambios, pero una firma
   Authenticode facilitaría verificar autor y evitar alertas de SmartScreen.
2. **No hay canal de actualización firmado.** Actualmente no existe un
   actualizador automático, lo cual evita una superficie remota pero obliga a
   verificar manualmente cada lanzamiento.
3. **Drivers externos.** HidHide y ViGEm operan a nivel de sistema; Nikaido solo
   debe enlazar a sus canales oficiales y nunca redistribuir binarios sin
   comprobar licencia, origen y firma.
4. **Mismo usuario de Windows.** Una cuenta ya comprometida puede modificar los
   archivos instalados por usuario. La firma de código y un instalador firmado
   son la siguiente defensa importante.

## Archivos principales modificados

`src/security_utils.py`, `src/profile_manager.py`, `src/macro_engine.py`,
`src/hidhide_manager.py`, `src/bluetooth_utils.py`, `src/crash_reporting.py`,
`src/game_profile_watcher.py`, `src/input_studio.py`, `src/light_effects.py`,
`src/trigger_engine.py`, `gui/ui_theme.py`, `gui/interface_editor.py`,
`gui/interface_renderer.py`, `gui/modern_app.py`, `main.py`, `build.py`,
`installer/Nikaido.iss`, `install.bat`, dependencias, CI y pruebas.
