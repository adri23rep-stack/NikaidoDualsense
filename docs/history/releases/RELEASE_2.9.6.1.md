# Nikaido DualSense 2.9.6.1 — hotfix Audio + HidHide

Esta versión corrige dos fallos observados en Windows después de 2.9.6.

## Audio

- Cada orden de mute se confirma leyendo de regreso `GetMute()`.
- Endpoints que ignoran la primera escritura se reintentan brevemente.
- Las escrituras globales vuelven a enumerar dispositivos para evitar wrappers COM obsoletos.
- Un micrófono que no expone volumen maestro ya no invalida su mute.
- Los errores ahora indican cuando Windows no confirmó el cambio.

## HidHide

- Detección directa en HKCR, con compatibilidad HKLM y fallback del servicio `HidHide`.
- Búsqueda en las carpetas históricas con y sin `e.U`.
- Reconocimiento seguro de `.venv\Scripts\python.exe` como runtime de Nikaido.
- Normalización de rutas NT devueltas por HidHide.
- El botón de compatibilidad ahora dice `Permitir Nikaido` porque el paquete fuente usa Python local.

## Diagnóstico

`DIAGNOSTICAR_AUDIO_HIDHIDE.bat` crea `diagnostico_audio_hidhide.json` sin modificar el mute ni la configuración de HidHide.
