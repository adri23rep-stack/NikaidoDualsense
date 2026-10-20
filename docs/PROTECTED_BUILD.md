# Compilación protegida secundaria

Nikaido conserva dos pipelines completamente separados:

| Variante | Comando | Salida |
|---|---|---|
| Desarrollo / normal | `COMPILAR_NIKAIDO.bat` | `release/` |
| Distribución protegida | `COMPILAR_NIKAIDO_PROTEGIDO.bat` | `release_protected/` |

La variante protegida usa **Nuitka** para convertir los módulos propios de
Python a código C y después a módulos/binarios nativos. No modifica `main.py`,
`src/`, `gui/` ni `build.py`; crea un pequeño punto de entrada temporal en una
ruta corta fuera del proyecto y lo elimina al terminar. Esto evita errores de
Windows al instalar PySide6 o generar archivos intermedios con nombres largos.

## Qué protege

- No distribuye archivos `.py`, `.pyw`, `.pyc` ni `.pyo`.
- Compila `main`, `gui`, `src` y `nikaido_version` como código nativo.
- Incluye de forma explícita las páginas cargadas con `importlib`.
- Mantiene los sprites y otros recursos como datos, porque la aplicación debe
  poder leerlos para mostrarlos.
- Valida el backend HID, la bandeja, Qt y la ausencia de código fuente antes de
  crear el ZIP.
- Genera un manifiesto SHA-256 de toda la distribución.

## Lo que no puede prometer

Ninguna aplicación que se ejecuta en el equipo del cliente es imposible de
analizar. Esta compilación eleva bastante la dificultad frente a PyInstaller,
pero alguien con experiencia, tiempo y herramientas nativas todavía podría
estudiar el ejecutable. La firma digital, activación y comprobación de propiedad
serán capas adicionales cuando el proyecto tenga presupuesto.

## Requisitos

1. Windows x64.
2. Python oficial de python.org, no la edición de Microsoft Store.
3. Doble clic en `COMPILAR_NIKAIDO_PROTEGIDO.bat`.

No ejecutes `install.bat` como requisito de la compilación protegida. El BAT
protegido crea y reutiliza su propio entorno en `%LOCALAPPDATA%\NKB`, aunque el
proyecto esté dentro de una carpeta profunda de Descargas. Puedes eliminar ese
entorno cuando quieras con `LIMPIAR_ENTORNO_PROTEGIDO.bat`.

La primera compilación puede solicitar la descarga de un compilador C compatible
y tardará bastante más que PyInstaller. Los archivos temporales nunca deben
compartirse.

## Instalador protegido

Usa `CREAR_INSTALADOR_PROTEGIDO.bat`. Necesita Inno Setup 6 y crea:

`release_protected/Nikaido_DualSense-<version>-Protected-Setup.exe`

El nombre “Protected” es solo para distinguir internamente el artefacto. El
producto instalado sigue apareciendo como **Nikaido DualSense**.
