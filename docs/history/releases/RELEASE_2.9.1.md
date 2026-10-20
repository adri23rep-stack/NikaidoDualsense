# Nikaido DualSense 2.9.1

Hotfix de inicio para la interfaz multidioma.

## Corregido

- `DashboardPage` ahora importa correctamente `tr` y `translate_widget_tree` desde `gui.i18n`.
- La GUI ya no cae a modo consola al crear la pestaña Nikaido Nexus del Dashboard.
- Los menús de favoritos del Dashboard pueden traducirse sin provocar otro `NameError` posterior.
- Se añadió una prueba de regresión que verifica los imports de internacionalización usados por el Dashboard.

Este hotfix conserva la curva visual reparada, Español/English/Português (Brasil), el asistente global y las optimizaciones de RAM de la serie 2.9.0.
