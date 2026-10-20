# Reporte de cambios — Nikaido DualSense 2.9.3

## Objetivo

Pulir la experiencia de primer inicio, corregir la lectura y presentación de batería, ordenar la raíz del proyecto y reducir la exposición del nombre legal en los textos de licencia visibles.

## Cambios implementados

### Primer inicio e idioma

- El idioma es ahora el paso 1 del wizard y ocupa una pantalla completa.
- Español, English y Português (Brasil) se presentan como tarjetas grandes.
- En una configuración nueva, no se puede avanzar, omitir ni cerrar el recorrido sin elegir explícitamente un idioma.
- La elección se guarda inmediatamente y sigue disponible en Ajustes para cambios posteriores sin reiniciar.

### Batería

- `ControllerState` distingue entre una lectura real de 0 % y una batería todavía desconocida mediante `battery_valid`.
- El primer arranque ya no muestra un 0 % falso mientras espera el primer reporte HID.
- Wizard, barra lateral y Dashboard muestran `—` o `Leyendo…` hasta recibir un valor válido.
- El cambio de lectura desconocida a válida también dispara la actualización de batería.

### Dashboard

- La batería tiene una tarjeta dedicada de ancho completo.
- Incluye porcentaje, barra de progreso y estado de carga.
- Firmware y conexión ocupan una segunda fila para evitar superposición en ventanas estrechas.
- Los estados dinámicos de batería se traducen en los tres idiomas.

### Organización del proyecto

- Reportes, notas, hotfixes, validaciones, cambios y roadmaps históricos se movieron a `docs/history/`.
- La raíz conserva principalmente código, licencias y accesos `.bat` de compilación e instalación.
- Se añadió un índice en `docs/history/README.md`.

### Licencia

- El titular se define legalmente dentro de cada idioma sin repetir su nombre al inicio.
- El nombre completo aparece una sola vez y únicamente en la última línea de cada licencia visible.
- El EULA multilingüe usado por Inno Setup también muestra el nombre una sola vez, al final de todo el documento.

### Compatibilidad conservada

- Asistente global de Nikaido y sus consejos.
- Optimización de RAM de la serie 2.7.
- Reparación de desconexión del DualSense.
- Curvas visuales de Input Studio.
- Pipeline protegido Nuitka, rutas cortas, pytest y reparación de ViGEm.

## Archivos principales modificados

- `src/connection_manager.py`
- `gui/main_window.py`
- `gui/pages/dashboard.py`
- `gui/pages/settings.py`
- `gui/i18n.py`
- `gui/design_system.py`
- `src/profile_manager.py`
- `nikaido_version.py`
- `installer/Nikaido.iss`
- `installer/NikaidoProtected.iss`
- `LICENSE` y EULAs
- `README.md`

## Validación

- 327 pruebas aprobadas.
- Compilación sintáctica completa con `python -m compileall` aprobada.
- La raíz no contiene reportes o hotfixes históricos sueltos.
- El manifiesto de integridad fue regenerado para la versión 2.9.3.

La lectura física de batería, escalado visual y compilación protegida final deben comprobarse en Windows con un DualSense real.
