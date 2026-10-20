# Nikaido DualSense 2.9.5.1 — hotfix de arranque GUI y audio

## Corregido

- La interfaz gráfica vuelve a abrir: `gui.design_system` exporta de nuevo todos los símbolos de apariencia usados por las páginas.
- `comtypes` queda declarado explícitamente como dependencia de Windows para el control del micrófono.
- `install.bat` comprueba HID, PySide6, pycaw, comtypes y el import completo de la GUI antes de marcar la instalación como correcta.
- El motor de audio muestra una instrucción útil cuando falta una dependencia en lugar de dejar únicamente un `ModuleNotFoundError` crudo.
- Se añadió una prueba de contrato que compara cada import solicitado a `design_system` con sus exports reales.
