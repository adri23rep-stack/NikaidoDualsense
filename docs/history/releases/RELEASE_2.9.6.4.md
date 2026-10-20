# Nikaido DualSense 2.9.6.4 — rutas cortas y monitor real

## Qué estaba fallando

La distribución fuente creaba `.venv` dentro de la carpeta extraída. Cuando el
ZIP quedaba dentro de una ruta larga de Descargas, los recursos QML de PySide6
superaban el límite histórico de rutas de Windows y `pip` terminaba con
`[Errno 2] No such file or directory` durante `PySide6_Essentials`.

El monitor del Dashboard tampoco enseñaba mediciones reales: multiplicaba por
cuatro la frecuencia de refresco de Qt, calculaba el supuesto lag como
`1000 / FPS`, mostraba siempre cero fallos y llamaba a un método inexistente de
la gráfica. Por eso los números cambiaban con la carga de la interfaz.

## Correcciones

- Nuevo `NIKAIDO_RUNTIME.bat` compartido por instalación, inicio, reparación,
  diagnóstico y compilación.
- Runtime aislado en `%LOCALAPPDATA%\NKB\rt` y temporales en una ruta corta.
- Compatibilidad de arranque con la antigua `.venv`, pero prioridad para el
  runtime corto.
- PySide6 fijado a `>=6.8.3,<6.9`.
- HidHide permite el Python exacto del runtime administrado y sigue rechazando
  el Python global.
- Dashboard alimentado por `get_diagnostics_snapshot()` y por las métricas
  reales de ViGEm.
- La gráfica muestra `pipeline_p95_ms` mediante `LatencyGraph.add_value()`.
- CPU medida sobre el proceso de Nikaido, no sobre todo Windows.

## Validación

- 422 pruebas automatizadas aprobadas, incluidas las pruebas Qt en modo offscreen.
- Compilación sintáctica completa de `main.py`, `src`, `gui` y `tests`.

La orden física de mute de micrófono y la sincronización del LED naranja de
2.9.6.3 permanecen sin cambios.
