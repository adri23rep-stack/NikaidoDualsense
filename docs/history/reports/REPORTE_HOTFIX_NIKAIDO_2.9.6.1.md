# Reporte de hotfix — Nikaido DualSense 2.9.6.1

## Causa del mute

El backend confiaba en que `IAudioEndpointVolume.SetMute` había funcionado si no lanzaba una excepción. Algunos endpoints USB/Bluetooth pueden ignorar temporalmente la primera escritura o quedar representados por un wrapper COM anterior después de una reconexión. Además, la lectura de volumen se hacía dentro de la misma operación: si el driver soportaba mute pero no volumen maestro, Nikaido trataba toda la orden como fallida.

## Corrección del mute

- Enumeración forzada antes de escrituras globales.
- Hasta tres intentos breves de `SetMute`.
- Confirmación obligatoria mediante `GetMute`.
- Lectura de volumen tolerante e independiente del mute.
- Restauración global con la misma verificación.

## Causa de HidHide

La búsqueda solo incluía el nombre histórico `Nefarius Software Solutions e.U`, aunque instalaciones válidas usan también `Nefarius Software Solutions`. Además, el paquete fuente corre realmente con `.venv\Scripts\python.exe`, pero el administrador de HidHide solo devolvía una ruta cuando Nikaido estaba compilado como EXE.

## Corrección de HidHide

- Consulta HKCR según la integración documentada por HidHide.
- Fallback de las claves HKLM y del servicio del driver.
- Búsqueda limitada y segura en ambas variantes de Program Files.
- Identificación del Python local `.venv` como runtime que puede agregarse a aplicaciones permitidas.
- Conversión de rutas `\Device\HarddiskVolume...` a letra de unidad para comparar la lista blanca.

## Archivos principales

- `src/audio_manager.py`
- `src/hidhide_manager.py`
- `gui/pages/system.py`
- `tools/diagnose_audio_hidhide.py`
- `DIAGNOSTICAR_AUDIO_HIDHIDE.bat`
- `tests/test_hotfix_2961_audio_hidhide.py`
