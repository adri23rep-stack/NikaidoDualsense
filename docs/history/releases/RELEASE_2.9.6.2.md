# Nikaido DualSense 2.9.6.2 — hotfix HidHide compilado

## Corregido

- La versión compilada registra `Nikaido.exe` en HidHide en lugar de dejar una entrada inválida a `python.exe`.
- Al activar el ocultamiento, Nikaido se permite primero para evitar perder acceso al DualSense.
- Se elimina únicamente la entrada antigua de Nikaido ubicada en la misma carpeta, sin tocar aplicaciones ajenas.
- Se interpreta correctamente la salida oficial de `--app-list`, `--dev-list`, `--dev-gaming` y `--cloak-state`.
- La detección del DualSense funciona con el JSON real de HidHideCLI.
- Se aceptan IDs Bluetooth `BTHENUM` y `BTHLEDEVICE`.
- Se detectan compilaciones PyInstaller y Nuitka aunque `sys.frozen` no esté disponible.
