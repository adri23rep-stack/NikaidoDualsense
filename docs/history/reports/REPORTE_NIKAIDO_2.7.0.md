# Reporte — Nikaido DualSense 2.7.0 Mascot Wizard Foundation

**Base usada:** Nikaido DualSense 2.6.2 Dashboard Pencil Favorites  
**Objetivo:** integrar a la mascota oficial dentro del wizard y dejar una base reutilizable para el resto del programa.

## Resultado visual y funcional

- El wizard ahora tiene un panel lateral permanente dedicado a Nikaido.
- Cada uno de los seis pasos usa una pose, título, mensaje e insignia distintos.
- La mascota apunta hacia el contenido cuando corresponde y celebra al finalizar.
- La pantalla de conexión muestra estado real, tipo de conexión y batería.
- El botón **Buscar ahora** inicia la detección del DualSense desde el wizard.
- Cuando el control aparece, Nikaido cambia a una pose feliz y confirma la conexión.
- La ventana creció para conservar espacio útil sin amontonar controles.

## Base reutilizable

Se añadió `MascotPanel` a `gui/components.py`. El componente:

- carga sprites mediante `resource_path`
- conserva proporciones
- usa escalado suave
- incluye globo de diálogo, nombre e insignia
- tiene fallback visual si un recurso no puede cargarse

Los 20 sprites se integraron dentro de:

- `assets/mascot/poses_a`
- `assets/mascot/poses_b`

Fueron normalizados y optimizados para la interfaz. Los nombres no contienen espacios ni acentos.

## Compatibilidad

- El onboarding subió de versión 2 a 3 para mostrar el nuevo recorrido a instalaciones existentes.
- No cambió el formato `.Nika`.
- No se modificaron emulación, macros, perfiles, gatillos, gyro ni rutas de AppData.
- PyInstaller ya empaquetaba el directorio completo `assets`, por lo que los sprites quedan incluidos.

## Pruebas

- 282 pruebas aprobadas.
- `compileall` correcto para `main.py`, `src`, `gui` y `tests`.
- 20/20 sprites verificados como PNG RGBA con transparencia real.
- Versiones sincronizadas en Python, `pyproject.toml` e Inno Setup.
- Límites arquitectónicos respetados.

## Validación pendiente en Windows

- Revisar la escala real de la mascota con DPI 100%, 125% y 150%.
- Comprobar el wizard en resoluciones pequeñas.
- Conectar un DualSense USB y Bluetooth durante el paso de conexión.
- Compilar con PyInstaller/Inno Setup y confirmar que los sprites aparezcan dentro del EXE.
