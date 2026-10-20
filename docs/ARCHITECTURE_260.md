# Arquitectura de interfaz — Nikaido 2.6

Nikaido 2.6 separa la interfaz Qt sin cambiar su comportamiento visible. La
versión 2.5.6 queda como referencia estable anterior a la migración.

## Estructura

- `gui/modern_app.py`: fachada pública compatible con imports antiguos.
- `gui/main_window.py`: ventana principal, navegación y coordinación de motores.
- `gui/components.py`: widgets visuales y componentes reutilizables.
- `gui/ui_common.py`: imports Qt y utilidades visuales compartidas, sin lógica.
- `gui/pages/dashboard.py`: Dashboard.
- `gui/pages/profiles.py`: perfiles y editor.
- `gui/pages/nexus.py`: Nikaido Nexus y mapper.
- `gui/pages/input.py`: Input Studio, calibración y Gyro Studio.
- `gui/pages/macros.py`: biblioteca y editor de macros.
- `gui/pages/device.py`: luces, vibración, gatillos y audio.
- `gui/pages/system.py`: automatización, HidHide, diagnóstico, emulación y herramientas.
- `gui/pages/settings.py`: asistente inicial y ajustes.

## Reglas de mantenimiento

1. `modern_app.py` no vuelve a recibir implementación de pantallas.
2. Las páginas hablan con los motores mediante `window`, igual que antes de la
   separación; no se duplicó lógica HID.
3. Los imports históricos desde `gui.modern_app` continúan funcionando.
4. Una nueva página debe vivir en `gui/pages`, registrarse en
   `NikaidoWindow._page_factories` y tener una prueba de arquitectura.
5. Los módulos Qt se incluyen explícitamente en PyInstaller.

## Qué no cambió

No se modificaron formatos `.Nika`, configuración, sensibilidad, macros,
perfiles, emulación, HidHide, feedback virtual ni controles físicos. Esta
versión es una migración estructural para reducir el riesgo de cambios futuros.
