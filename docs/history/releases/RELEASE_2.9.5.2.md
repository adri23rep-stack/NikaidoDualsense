# Nikaido DualSense 2.9.5.2 — hotfix de instalación de audio

## Causa

`requirements-runtime.txt` declaraba `pycaw>=20251023,<2027`. Pycaw usa versiones basadas en fecha, por lo que `20251023` es numéricamente mayor que `2027`. Ninguna versión podía satisfacer las dos condiciones y pip detenía la instalación antes de instalar `pycaw` y `comtypes`.

## Corregido

- `pycaw` queda fijado como `pycaw==20251023` únicamente en Windows.
- Se conserva `comtypes>=1.4.10,<2` para Core Audio.
- `install.bat` y `REPARAR_GUI_Y_AUDIO.bat` siguen leyendo una sola fuente de dependencias.
- Se añadió una regresión que valida el pin publicado de pycaw.
- Se añadió una comprobación general para detectar rangos contradictorios en todas las dependencias de ejecución.
- Versión actualizada a 2.9.5.2 en aplicación, proyecto e instaladores.

## Uso

En una carpeta extraída limpia, ejecutar `install.bat`. Si ya existe `.venv`, puede ejecutarse `REPARAR_GUI_Y_AUDIO.bat`; pip completará lo que faltó sin modificar el Python global.
