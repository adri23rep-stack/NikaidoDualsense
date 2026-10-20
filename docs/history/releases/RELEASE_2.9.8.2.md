# Nikaido DualSense 2.9.8.2 Beta 1 — Profile Studio Hotfix

## Corrección principal
- Corrige el bloqueo al abrir la pestaña **Perfiles**.
- La pantalla usaba la clave visual inexistente `violet`; la paleta oficial usa `accent2`.
- El error ocurría durante la construcción inicial de las estadísticas y nuevamente en el panel lateral.

## Prevención
- Se añadió una prueba automática que compara todas las claves `C[...]` usadas por Profile Studio contra la paleta real de Nikaido.
- Se conservan todas las mejoras de Profile Studio 2.0, perfiles nuevos, iconos vectoriales y animaciones compartidas.

## Límites
- No se afirma prueba física con un DualSense ni compilación del instalador en Windows.
