# Nueva interfaz Qt de Nikaido

La interfaz activa vive en `gui/modern_app.py` y usa PySide6. `main.py` conserva
el mismo contrato con el backend: recibe los gestores ya inicializados, conecta
el icono de bandeja y apaga todos los motores de forma ordenada.

## Qué está conectado

- Dashboard, batería, conexión, sticks, gatillos y telemetría en vivo.
- Aplicar, crear, importar, exportar y eliminar perfiles personales.
- Remapeo directo del control virtual Xbox/DS4.
- Input Studio por stick y perfil, incluida calibración de drift.
- Gyro Studio, calibración, recentrado y prueba de salida.
- Grabación, guardado, reproducción y eliminación de macros.
- Luz RGB e indicadores blancos de jugador.
- Vibración oficial independiente de L2/R2 y sus zonas de activación.
- Monitor HID, herramientas de conexión, Bluetooth y emulación.
- Inicio con Windows, bandeja y preferencias persistentes.

Audio aparece como función en preparación porque el backend actual no controla
el dispositivo de audio de Windows. La pantalla no presenta controles falsos.

## Desarrollo

```cmd
pip install -r requirements.txt
python main.py
```

Para generar el ejecutable:

```cmd
python build.py
```

El resultado validado queda en `release/Nikaido/Nikaido.exe`. No ejecutes copias temporales de `build`, `dist` o `.nikaido_build`.

## Interfaz anterior

`gui/app.py` se conserva temporalmente como referencia y para facilitar la
comparación durante la migración. Ya no es importada por `main.py` ni se incluye
como dependencia del ejecutable.
