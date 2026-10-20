# Nikaido DualSense 2.5.6 — Security Hardening

Esta versión endurece la base 2.5 sin cambiar la sensación del mouse, gyro,
Nexus, perfiles, vibración ni KeyBridge.

## Archivos y paquetes no confiables

- Los perfiles `.Nika` y temas validan rutas, nombres ambiguos de Windows,
  archivos cifrados, duplicados, tamaño descomprimido y relación de compresión.
- Se rechazan rutas absolutas, traversal `..`, ADS de NTFS, nombres reservados
  como `CON`/`NUL` y paquetes diseñados como ZIP bomb.
- JSON, macros, reglas, perfiles, curvas, efectos y secciones tienen límites de
  tamaño, profundidad y cantidad.
- `NaN`, `Infinity` y valores físicos fuera de rango ya no llegan a los motores.
- Imágenes y GIF se validan antes de decodificarse y tienen presupuestos de
  píxeles, cuadros y memoria.
- Los temas empaquetados no pueden leer imágenes fuera de su propia carpeta.

## Herramientas externas y privilegios

- HidHide ya no confía en ejecutables encontrados mediante `PATH` ni en rutas
  registradas por el usuario. Solo acepta herramientas oficiales ubicadas bajo
  `Program Files` y abre la página oficial para instalar.
- Las operaciones Bluetooth usan el PowerShell del sistema mediante una ruta
  explícita y un conjunto fijo de comandos internos.
- La reparación Bluetooth dejó de borrar las claves globales de emparejamiento.
- El instalador normal funciona por usuario y no solicita administrador.
- `install.bat` usa un entorno virtual local y no modifica paquetes globales.

## Privacidad e integridad

- Logs y reportes ocultan rutas de usuario y caracteres de control.
- Configuración, macros, temas e imágenes usan escrituras atómicas donde aplica.
- Las distribuciones incluyen SHA-256 por archivo dentro de `MANIFEST.json`.
- CI ejecuta pruebas, Ruff, Bandit y `pip-audit` en Windows.
- Pillow requiere 12.2.0 o posterior dentro de la rama 12.x.

## Validación

- 263 pruebas automatizadas aprobadas.
- Compilación completa de Python aprobada.
- Ruff crítico aprobado.
- Bandit: 0 hallazgos altos y 0 medios.

La prueba de HID, ViGEm, HidHide, Bluetooth y el instalador sigue necesitando un
Windows real con los controladores y el DualSense conectado.
