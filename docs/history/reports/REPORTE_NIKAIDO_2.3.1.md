# Reporte técnico — Nikaido DualSense 2.3.1

## Problema corregido

La opción histórica `minimize_to_tray` se aplicaba al botón cerrar. Por eso presionar × ocultaba la ventana, pero dejaba correctamente el proceso, la bandeja y los motores en ejecución. Aunque era el comportamiento configurado, visualmente parecía que Nikaido se había cerrado.

## Solución

Se separaron las intenciones de ventana:

- `request_minimize()` decide entre bandeja o barra de tareas.
- `request_close()` siempre llama al apagado completo.
- `closeEvent()` usa la ruta de cierre real.
- El apagado detiene primero motores y bandeja; Qt se cierra al final.
- Si el bucle Qt sale por otra causa, `main.py` ejecuta `shutdown()` como respaldo.

No se añadió un cierre forzado mediante `os._exit()`: Nikaido sigue liberando recursos de forma limpia y guardando la configuración antes de terminar.

## Nuevo asistente de bienvenida

Se añadió `WelcomeWizard`, un diálogo modal no bloqueante respecto al arranque de motores, con seis pantallas y navegación Atrás/Siguiente.

Incluye:

- explicación de funciones principales;
- ajustes rápidos conectados al `ProfileManager` real;
- previsualización de apariencia en vivo;
- selección de imagen de fondo;
- accesos finales a Dashboard, Nexus, Gyro Studio y Ajustes;
- repetición manual desde Ajustes;
- control de versión del onboarding.

El wizard respeta inicio minimizado: no aparece encima del escritorio cuando la aplicación está oculta en la bandeja, sino al mostrar la ventana.

## Archivos principales modificados

- `gui/modern_app.py`
- `gui/design_system.py`
- `src/profile_manager.py`
- `main.py`
- `nikaido_version.py`
- `README.md`
- `docs/history/releases/RELEASE_2.3.1.md`
- `docs/ONBOARDING.md`
- `tests/test_onboarding_and_exit_231.py`

## Compatibilidad

- `APP_VERSION`: 2.3.1
- `CONFIG_VERSION`: 2.0.0
- `NIKA_FORMAT_VERSION`: 1
- La clave `minimize_to_tray` se mantiene; solo cambia su interpretación visual.
- No se modificó HID, batería, ViGEm, passthrough DS4, Gyro Engine, Nexus, macros ni perfiles `.Nika`.

## Validación

- 177 pruebas aprobadas.
- `py_compile` y `compileall` correctos.
- Prueba del orden real de apagado: bandeja antes de interfaz Qt.
- Pruebas de separación cerrar/minimizar.
- Pruebas de valores predeterminados y persistencia del asistente.

La comprobación física final del ejecutable debe realizarse en Windows para confirmar que el proceso desaparece del Administrador de tareas tras presionar ×.
