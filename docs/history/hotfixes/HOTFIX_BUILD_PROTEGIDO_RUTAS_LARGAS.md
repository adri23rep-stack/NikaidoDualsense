# Hotfix del compilador protegido: rutas largas de Windows

## Problema

Cuando el proyecto estaba dentro de una ruta profunda, por ejemplo dentro de
`Downloads/Nikaido_DualSense-2.9.2-Protected-Build-Pipeline/...`, `pip` no podía
instalar PySide6. Algunos recursos QML de Qt tienen nombres internos muy largos
y la suma completa superaba el límite histórico de rutas de Windows.

El error aparecía durante la instalación de `PySide6_Essentials` y no estaba
relacionado con el código de Nikaido ni con Nuitka.

## Solución

`COMPILAR_NIKAIDO_PROTEGIDO.bat` ahora prepara su propio entorno aislado en una
ruta corta fuera del proyecto:

- Entorno Python: `%LOCALAPPDATA%\NKB\v292`
- Temporales de Nuitka: `%LOCALAPPDATA%\NKB\w292`
- Caché de pip: `%LOCALAPPDATA%\NKB\pip`

La compilación protegida ya no depende de `install.bat` ni de la `.venv` local.
El código fuente y el pipeline normal siguen intactos.

## Uso

1. Extrae el proyecto.
2. Ejecuta `COMPILAR_NIKAIDO_PROTEGIDO.bat` directamente.
3. No es necesario ejecutar `install.bat` antes.
4. Para borrar el entorno externo después, usa
   `LIMPIAR_ENTORNO_PROTEGIDO.bat`.

Una `.venv` local incompleta de un intento anterior puede borrarse sin afectar
perfiles ni ajustes de Nikaido. El nuevo compilador protegido la ignora.
