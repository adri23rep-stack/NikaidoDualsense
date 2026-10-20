# Nikaido DualSense 2.3.1

Esta versión corrige el ciclo de cierre de la aplicación y añade un asistente de bienvenida integrado para presentar las funciones principales y configurar lo esencial.

## Cierre y bandeja

- El botón **cerrar (×)** ahora siempre termina Nikaido por completo.
- Cerrar libera conexión, emulación, gyro, luces, gatillos, mapper, perfiles por juego y bandeja antes de salir.
- El botón **minimizar (−)** mantiene el comportamiento opcional de bandeja.
- Si la bandeja no está disponible, minimizar usa la barra de tareas normal de Windows.
- La opción anterior `minimize_to_tray` se conserva para compatibilidad, pero ahora controla únicamente el botón minimizar.
- Si Qt termina mediante una ruta externa, Nikaido ejecuta igualmente el apagado completo de los módulos.
- La interfaz Qt se detiene al final, después de los motores y del icono de bandeja, para evitar callbacks tardíos.

## Asistente de bienvenida

El nuevo recorrido inicial presenta Nikaido en seis pasos:

1. Bienvenida y resumen general.
2. Conexión, inicio y comportamiento de ventana.
3. Perfiles `.Nika` y Nikaido Nexus.
4. Gyro Studio, Flick Stick, macros y diagnóstico.
5. Apariencia Studio y personalización rápida.
6. Pantalla final con accesos directos.

El asistente permite configurar:

- conexión automática;
- inicio minimizado;
- minimizar a bandeja;
- perfiles automáticos por juego;
- vibración general;
- color de acento;
- densidad visual;
- reducción de animaciones;
- barra lateral compacta;
- imagen de fondo.

Los cambios visuales se previsualizan en vivo. Omitir o cerrar el recorrido restaura la apariencia anterior si no se guardó. Al finalizar, todo se persiste mediante el sistema de guardado normal de Nikaido.

## Repetir el recorrido

En **Ajustes → Datos** se añadió:

`Volver a iniciar el asistente de bienvenida`

El usuario puede abrirlo cuantas veces necesite para probarlo o volver a revisar las funciones.

## Compatibilidad

- `CONFIG_VERSION` permanece en 2.0.0.
- `.Nika` permanece en versión 1.
- Se conserva la clave `minimize_to_tray` para perfiles y configuraciones existentes.
- No se cambió la ruta HID, ViGEm, gyro, macros, perfiles ni Input Studio.

## Validación

- 177 pruebas automatizadas aprobadas.
- Todos los módulos Python compilan correctamente.
- Pruebas específicas para cierre, orden de apagado, ajustes del wizard y compatibilidad de configuración.
