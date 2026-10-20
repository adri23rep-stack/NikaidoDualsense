# Reporte — Nikaido DualSense 2.9.0

**Base usada:** Nikaido DualSense 2.8.0 Global Assistant  
**Objetivos:** reparar la curva visual de Input Studio e incorporar Español, English y Português (Brasil).

## Bug reparado: curva visual

La gráfica anterior conservaba siempre los puntos de la curva personalizada y se deshabilitaba cuando el preset no era `custom`. Eso provocaba dos problemas:

1. Cambiar entre Lineal, Exponencial y Agresiva no cambiaba realmente el dibujo.
2. El usuario no podía comenzar a arrastrar puntos mientras la gráfica estaba deshabilitada.

La solución separa la curva visible de los puntos editables:

- Lineal, Exponencial y Agresiva se muestrean con 49 puntos para una vista suave.
- Las fórmulas coinciden con `src/input_studio.py`.
- Personalizada usa los puntos guardados y habilita el arrastre.
- La gráfica permanece activa en todos los modos.
- Una referencia lineal punteada facilita comparar la respuesta.

El editor se movió a `gui/curve_editor.py` para mantener `gui/components.py` dentro del límite arquitectónico.

## Sistema de idiomas

Se añadió `gui/i18n.py` con:

- normalización segura de códigos de idioma;
- traducciones exactas para la interfaz principal;
- traducción de frases comunes para páginas secundarias;
- actualización de labels, botones, tooltips, accesibilidad, combos, pestañas, tablas y menús;
- conservación del texto fuente para cambiar de idioma varias veces sin reconstruir la interfaz.

### Wizard

- Selector visible en el encabezado.
- Cambio inmediato de pasos, diálogos de Nikaido, estado de conexión y botones.
- La elección se guarda incluso al omitir el recorrido.

### Ajustes

- Nueva tarjeta `IDIOMA / LANGUAGE`.
- Español, English y Português (Brasil).
- No requiere reiniciar.

### Ventana principal

- La navegación y el título de página cambian al instante.
- Las páginas pesadas cargadas después reciben el idioma activo.
- El buscador Ctrl+K reconstruye sus entradas traducidas.
- El asistente muestra consejos y acciones en el idioma activo.

## Archivos principales

- `gui/i18n.py`
- `gui/curve_editor.py`
- `gui/components.py`
- `gui/main_window.py`
- `gui/pages/input.py`
- `gui/pages/settings.py`
- `gui/pages/dashboard.py`
- `src/profile_manager.py`
- `build.py`
- `tests/test_i18n_and_curve_290.py`

## Validación

- 302 pruebas aprobadas.
- Compilación Python correcta para `main.py`, `src`, `gui` y `tests`.
- Versiones sincronizadas en Python, `pyproject.toml` e Inno Setup.
- Nuevos módulos incluidos explícitamente para PyInstaller.

## Pendiente en Windows

- Confirmar visualmente textos largos en 1080p y escalado 125/150%.
- Probar cambio repetido Español → English → Português (Brasil) → Español.
- Verificar el arrastre de la curva personalizada con mouse real.
