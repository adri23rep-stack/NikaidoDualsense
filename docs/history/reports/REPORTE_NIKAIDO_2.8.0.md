# Reporte — Nikaido DualSense 2.8.0

**Base usada:** Nikaido DualSense 2.7.2 RAM Optimization  
**Objetivo:** integrar a Nikaido como asistente opcional en toda la aplicación.

## Elección al terminar el wizard

Al finalizar o pulsar **Omitir por ahora**, aparece una pantalla que pregunta si el usuario quiere a Nikaido como asistente.

- **Sí, acompáñame:** Nikaido cambia a pose feliz, confirma la activación y programa sus consejos.
- **No, gracias:** Nikaido usa la pose triste/preocupada, muestra “¿Por qué? 😭” y abre el programa con la asistente desactivada.
- La elección se guarda en `settings.assistant`.

## Asistente global

Se añadió un panel compacto que aparece ocasionalmente en la esquina inferior derecha sin bloquear la navegación. Los consejos incluyen funciones poco visibles como:

- `Ctrl + K` para abrir el buscador rápido.
- Capas, gestos y acciones avanzadas de Nikaido Nexus.
- Contenido guardado dentro de perfiles `.Nika`.
- Favoritos editables del Dashboard.
- HidHide para evitar doble entrada.
- `Ctrl + M` durante Mouse → Gyro.
- Macros con palancas y tiempos editables.
- Curvas y zonas muertas de Input Studio.
- Herramientas del Centro de diagnóstico.

Cada aviso puede cerrarse y ofrece un botón para abrir directamente la sección relacionada. Se oculta automáticamente después de 22 segundos y vuelve a aparecer con un intervalo predeterminado de 12 minutos.

## Ajustes y memoria

- Nuevo interruptor **Usar a Nikaido como asistente**.
- Nuevo interruptor **Mostrar consejos ocasionales**.
- La asistente inicia desactivada en configuraciones nuevas hasta que el usuario decida.
- Los sprites compactos se decodifican cerca de su tamaño visible.
- Al desactivar o cerrar la aplicación se liberan sus `QPixmap`.
- El panel vive en un módulo separado para mantener revisable la arquitectura.

## Validación

- 296 pruebas aprobadas.
- Compilación Python correcta.
- Versiones sincronizadas en Python, `pyproject.toml` e Inno Setup.
