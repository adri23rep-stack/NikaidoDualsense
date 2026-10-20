# Reporte de hotfix — Nikaido DualSense 2.9.5.1

## Problemas reportados

1. La GUI no abría y terminaba en modo consola con:
   `ImportError: cannot import name 'APPEARANCE_PRESETS' from 'gui.design_system'`.
2. El motor de audio mostraba:
   `ModuleNotFoundError: No module named 'comtypes'`.

## Causa del fallo de GUI

`gui/ui_common.py` importa desde `gui/design_system.py` cuatro símbolos de apariencia:

- `APPEARANCE_PRESETS`
- `DEFAULT_APPEARANCE`
- `appearance_background_signature`
- `appearance_style_signature`

Los cuatro existían en `src/appearance.py`, pero `gui/design_system.py` solo reenviaba `ACCENT_PALETTES` y `normalize_appearance`. Por eso Python detenía el import de la interfaz antes de crear la ventana.

Las pruebas anteriores revisaban principalmente estructura y contenido del código, pero el entorno de validación no tenía PySide6 instalado. Eso permitió que el contrato roto entre módulos no se detectara.

## Reparaciones realizadas

- Restaurados los cuatro exports faltantes en `gui/design_system.py`.
- Añadido `__all__` para documentar y conservar los exports portables de apariencia.
- Creada una prueba que analiza todos los imports dirigidos a `design_system` y falla si algún símbolo solicitado no existe.
- Creada una prueba real de import y apertura de ventana cuando PySide6 está disponible.
- Declarado `comtypes>=1.4.10,<2` explícitamente en `requirements-runtime.txt` para Windows.
- `install.bat` ahora verifica HID, PySide6, pycaw, comtypes y el import completo de la GUI.
- Añadido `REPARAR_GUI_Y_AUDIO.bat` para reparar el entorno local con doble clic.
- El motor de audio ahora muestra una instrucción útil cuando falta una dependencia.
- Versión actualizada a `2.9.5.1` en aplicación, proyecto e instaladores.

## Validación

- Suite completa: 381 pruebas aprobadas y 1 prueba GUI omitida únicamente porque el entorno base no tenía PySide6.
- Prueba GUI con PySide6 6.11.1 instalada temporalmente: 4/4 aprobadas.
- Import real de `gui.modern_app`: aprobado.
- Creación y visualización de `NikaidoWindow` con plataforma Qt fuera de pantalla: aprobada.
- Ruff: sin errores.
- `compileall`: aprobado.
- ZIP extraído y validado nuevamente antes de entregar.

## Limitación honesta

El control real de Core Audio, `comtypes`, pycaw, USB/Bluetooth y el DualSense físico solo puede verificarse completamente en Windows. En este entorno se validaron la declaración de dependencias, el flujo de instalación, los imports de GUI y la lógica mediante pruebas, pero no se controló un micrófono físico.
