# Hotfix 2.1.4 — Detección DualSense en el ejecutable

## Problema corregido
La versión ejecutada desde Python detectaba el DualSense, pero el ejecutable generado por PyInstaller podía abrir normalmente y permanecer en `Buscando`.

La causa era la diferencia entre los dos backends HID instalados:

- `pydualsense` importa `hidapi`, un wrapper CFFI que busca `hidapi.dll` externamente.
- El proyecto y PyInstaller ya incluían `hid`, la extensión de `cython-hidapi`.
- Si `hidapi.dll` no estaba en el entorno del ejecutable, la importación de `pydualsense` fallaba y Nikaido ocultaba el error al entrar en modo simulación.

## Solución

### Adaptador HID interno
Se añadió `src/hid_backend.py`.

- Prueba primero el backend original `hidapi`.
- Si su DLL no puede cargarse, crea una API compatible usando `hid`.
- Implementa las operaciones que necesita `pydualsense`:
  - enumerar dispositivos;
  - abrir por VID/PID o ruta;
  - leer y escribir reportes;
  - consultar fabricante, producto y número de serie;
  - feature reports;
  - cierre seguro.

### Empaquetado reforzado
`build.py` ahora:

- incluye explícitamente `hid`;
- incluye el adaptador `src.hid_backend`;
- recoge los submódulos dinámicos de `pydualsense`, incluido `hidguardian`;
- rechaza el build si no existe `hid*.pyd` dentro de `_internal`;
- ejecuta el `.exe` recién generado con un auto-test HID;
- comprueba que el ejecutable puede importar `pydualsense`, importar `hidguardian` y enumerar HID;
- no genera el ZIP final si el auto-test falla.

### Errores visibles
Si ninguno de los backends puede arrancar, la interfaz ahora muestra el motivo real mediante un aviso no modal, en vez de quedarse silenciosamente en `Buscando`.

### Diagnóstico
El reporte del Centro de diagnóstico ahora incluye:

- backend HID utilizado;
- si se está usando el adaptador;
- disponibilidad de `pydualsense`;
- error de importación;
- último error al abrir el control.

## Compatibilidad

- No cambia perfiles `.Nika`.
- No cambia macros.
- No cambia giroscopio ni passthrough DS4.
- No cambia emulación, Input Studio ni latencia.
- `CONFIG_VERSION` permanece en `2.0.0`.
- `NIKA_FORMAT_VERSION` permanece en `1`.

## Compilación

1. Ejecuta `install.bat` una vez para actualizar dependencias.
2. Ejecuta `COMPILAR_NIKAIDO.bat`.
3. Usa únicamente `release\\ABRIR_NIKAIDO.bat` o `release\\Nikaido\\Nikaido.exe`.

Durante la compilación aparecerá una línea similar a:

`Auto-test HID OK: cython-hidapi-compat`

La cantidad de dispositivos Sony puede ser cero si el control no está conectado durante la compilación; eso no invalida el build.

## Validación

- 140 pruebas automatizadas aprobadas.
- Compilación sintáctica completa correcta.
- Auto-test HID integrado en el ejecutable de Windows.
