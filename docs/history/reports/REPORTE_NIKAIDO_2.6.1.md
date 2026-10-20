# Reporte — Nikaido DualSense 2.6.1

**Base:** Nikaido 2.6.0 Architecture Foundation  
**Alcance:** Dashboard y persistencia de accesos favoritos.

## Bug corregido

La tarjeta de perfil activo solo escribía `profile.icon` dentro de un `QLabel`. Aunque el perfil tuviera `image_path`, el Dashboard nunca creaba un `QPixmap`. Ahora carga la imagen, la escala suavemente a la tarjeta y conserva el icono como respaldo.

## Dashboard personalizable

La antigua lista fija de Input Studio, Gyro, Macros, Luces, Vibración, Gatillos y Audio fue retirada del arranque. El área conserva Nikaido Nexus como primera pestaña fija y añade un botón `＋` con menú para elegir accesos.

Los destinos se almacenan en `settings.dashboard.favorite_tabs`. La lista se limpia al cargar para ignorar valores desconocidos y duplicados. Las pestañas añadidas muestran una `×`; Nexus no muestra botón de cierre y el controlador también ignora cualquier solicitud de cerrar el índice cero.

## Validación

- 274 pruebas aprobadas.
- Compilación de fuentes correcta.
- AST y compilación de todos los módulos correctos.
- APIs de pestañas y menú verificadas contra la documentación oficial de Qt for Python.
- Ruff y Bandit no están instalados en este entorno; la base 2.6.0 sí los había aprobado antes de este hotfix.

## Pendiente en Windows

Este entorno no contiene PySide6, así que la apertura visual real debe comprobarse en Windows: imagen recortada, menú `＋`, cierre de favoritos, reinicio de la aplicación y permanencia de Nexus.
