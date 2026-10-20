# Roadmap competitivo de Nikaido DualSense

Revisión del código: **Nikaido DualSense 2.4.0 – KeyBridge**  
Objetivo: competir de frente con **DSX/DualSenseX** y **DS4Windows** sin perder la identidad de Nikaido.

## Estado actual

Nikaido ya tiene una base bastante seria:

- Emulación Xbox 360 y DualShock 4.
- Perfiles completos `.Nika` con imagen, luces, macros, gatillos, gyro e Input Studio.
- Nikaido Nexus con capas, gestos, validación, copiar/pegar y deshacer/rehacer.
- Macros con botones, sticks, gatillos, tiempos y activadores.
- Gyro Aim, Flick Stick, passthrough DS4 y mouse a gyro.
- Curvas, deadzones, anti-deadzone, sensibilidad, inversión y calibración.
- Efectos de luz y gatillos adaptativos por separado.
- Diagnóstico de HID, ViGEm, latencia promedio y p95.
- KeyBridge para convertir teclado y mouse en mando virtual.
- 189 pruebas automatizadas aprobadas y compilación sintáctica limpia.

## Lo que Nikaido ya hace especialmente bien

1. **El formato `.Nika`** puede ser una ventaja de marca real si se convierte en el formato para compartir perfiles completos.
2. **Nexus** es una mejor base visual que el editor clásico de DS4Windows.
3. **Diagnóstico** tiene más detalle que el que suele mostrar una app de controles normal.
4. **KeyBridge** permite entrar también al mercado de usuarios de teclado y mouse.
5. **Gatillos multizona y luces animadas** hacen que Nikaido se sienta más enfocado en DualSense que un mapper genérico.

---

# Prioridad 0 — Antes de añadir funciones gigantes

## 1. Laboratorio de pruebas físicas

Crear una matriz automática y manual con:

- USB y Bluetooth.
- Conectar, desconectar, dormir y reconectar.
- Xbox 360, DS4 y sin emulación.
- Botones, sticks, gatillos, gyro, touchpad, batería, luces y vibración.
- Sesiones largas de 1, 4 y 8 horas.
- Medición de latencia, paquetes perdidos y consumo de CPU/RAM.

Las 189 pruebas actuales pasan, pero la mayoría valida lógica con simulaciones. El propio reporte 2.4.0 reconoce que KeyBridge y ViGEm todavía necesitan prueba física en Windows.

## 2. Dividir `gui/modern_app.py`

Actualmente tiene más de **10,000 líneas**. Separarlo en:

- `gui/pages/dashboard.py`
- `gui/pages/profiles.py`
- `gui/pages/nexus.py`
- `gui/pages/input_studio.py`
- `gui/pages/gyro.py`
- `gui/pages/macros.py`
- `gui/pages/lights.py`
- `gui/pages/triggers.py`
- `gui/pages/emulation.py`
- `gui/pages/diagnostics.py`
- `gui/pages/settings.py`

Esto reducirá errores cruzados y hará más fácil añadir funciones sin romper otra pestaña.

## 3. Dejar de esconder errores importantes

En los módulos activos hay:

- **136** manejadores generales de errores.
- **35** casos que silencian el error completamente con `pass`.

No todos son malos, especialmente durante el cierre, pero los relacionados con HID, ViGEm, macros, gyro y Bluetooth deberían registrar el problema y mostrar una solución en Diagnóstico.

## 4. Automatizar la calidad del proyecto

Añadir:

- `pyproject.toml`.
- Archivo de dependencias bloqueadas.
- GitHub Actions para pruebas y compilación.
- Revisión de estilo y tipos.
- Archivo `LICENSE` real; el README dice MIT pero el ZIP no lo incluye.
- Generación automática de versión para que el README no diga 2.3.2 cuando la app es 2.4.0.
- Publicación con hashes y firma digital.

## 5. Instalador profesional

Crear un instalador que:

- Instale Nikaido.
- Revise ViGEmBus y HidHide.
- Explique el doble input.
- Detecte conflictos con Steam Input, DS4Windows y DSX.
- Permita reparar drivers.
- Cree accesos directos y arranque con Windows.
- Desinstale limpiamente sin borrar perfiles del usuario.

---

# Prioridad 1 — Funciones necesarias para competir de verdad

## 6. DualSense virtual

Esta debe ser la función estrella futura.

Añadir una tercera salida virtual:

- Xbox 360.
- DualShock 4.
- **DualSense virtual**.

Debe conservar:

- Touchpad.
- Gyro y acelerómetro.
- Gatillos adaptativos.
- Vibración háptica.
- Audio del control.
- Botones especiales.

Requiere crear una capa de salida independiente del actual `vgamepad`, por ejemplo:

- `XboxOutputBackend`
- `DS4OutputBackend`
- `DualSenseOutputBackend`

## 7. Audio y Haptics Studio

La pantalla Audio actual reconoce que todavía no controla nada. Convertirla en un módulo real con:

- Selección de salida de audio del DualSense.
- Volumen de audífonos.
- Nivel y mute del micrófono.
- Monitoreo del micrófono.
- Estado del botón mute y su LED.
- Audio a vibración háptica.
- Rumble a hápticos.
- Ecualizador háptico por graves, medios y agudos.
- Intensidad separada izquierda/derecha.
- Presets para disparos, motores, música y películas.

## 8. Devolver la vibración del juego al control físico

Ahora Nikaido puede mandar vibración manual, pero el emulador no registra la respuesta de vibración que envía el juego al mando virtual.

Añadir:

1. Lectura del feedback del control virtual.
2. Conversión de motores Xbox/DS4 a vibración del DualSense.
3. Mezcla con efectos de perfil y gatillos.
4. Límites para evitar saturación.
5. Monitor en vivo dentro de Diagnóstico.

## 9. Soporte completo para DualSense Edge

Añadir:

- Detección independiente del Edge.
- Botones traseros.
- Botones Fn.
- Perfiles por control.
- Remapeo de palancas traseras.
- Identificación por número de serie.
- Pruebas USB y Bluetooth.

## 10. Múltiples controles

La arquitectura actual gira alrededor de un solo objeto `pydualsense()` y un solo gamepad virtual.

Crear:

- Lista de controles detectados.
- Una tarjeta por control.
- Perfil independiente por control.
- Color y número de jugador por dispositivo.
- Emulación independiente.
- Asignación de mando 1, 2, 3 y 4.
- Bloqueo para impedir que dos controles escriban al mismo slot virtual.

## 11. HidHide integrado

Añadir una pantalla de “Evitar doble input” con:

- Estado del driver.
- Instalación y reparación.
- Lista de dispositivos ocultos.
- Lista blanca de Nikaido.
- Prueba automática de doble input.
- Activación por perfil o por juego.
- Botón para restaurar todo si algo sale mal.

## 12. Modo nativo híbrido

Permitir que un juego siga viendo el DualSense físico para conservar sus gatillos/hápticos nativos mientras Nikaido usa botones concretos como teclado, macros o acciones del sistema.

Modos sugeridos:

- Nativo sin cambios.
- Nativo + acciones extras.
- Nativo + remapeo selectivo.
- Emulación completa.
- Emulación con DualSense virtual.

## 13. Touchpad avanzado

El touchpad actual usa un dedo para mover el mouse y el clic físico como clic izquierdo.

Añadir:

- Dos dedos.
- Tap y doble tap.
- Clic izquierdo, derecho y medio.
- Scroll vertical y horizontal.
- Zonas izquierda, centro y derecha.
- Swipe arriba, abajo, izquierda y derecha.
- Pinch para zoom.
- Gestos asignables en Nexus.
- Touchpad DS4 virtual con dos contactos.

## 14. Perfiles automáticos 2.0

El watcher actual revisa procesos cada 3 segundos, toma la primera coincidencia y deja activo el último perfil cuando el juego se cierra.

Mejorarlo con:

- Ventana que está al frente, no cualquier proceso abierto.
- Prioridades cuando hay varios juegos o launchers.
- Restaurar el perfil anterior al cerrar el juego.
- Reglas por ruta completa, nombre, Steam AppID y UWP.
- Retraso configurable al entrar/salir.
- Perfil temporal para overlays y menús.
- Perfil por control.
- Historial que explique por qué cambió el perfil.

## 15. KeyBridge 2.0

Cambiar la captura principal de `GetAsyncKeyState` a Raw Input para mejorar precisión y distinguir dispositivos.

Añadir:

- Elegir teclado y mouse concretos.
- Mouse crudo sin aceleración de Windows.
- Curvas de mouse a stick.
- Aceleración configurable.
- Aim y conducción como modos distintos.
- Teclas para valores analógicos parciales.
- Cambio automático por juego.
- Overlay pequeño de estado.
- Bloqueo de tecla Windows y combinaciones molestas.
- Pausa automática al escribir en chats.

---

# Prioridad 2 — Convertir Nikaido en plataforma

## 16. Nikaido Hub

Una biblioteca para compartir archivos `.Nika`:

- Buscar por juego.
- Calificaciones.
- Versiones.
- Autor y descripción.
- Capturas.
- Filtros por gyro, macros, luces y gatillos.
- Ver contenido antes de importar.
- Firma y revisión de seguridad.
- Reportar perfiles dañinos o engañosos.

Puede comenzar sin cuentas: un repositorio oficial descargable desde la app.

## 17. API para juegos y mods

Crear una API local por UDP, WebSocket o named pipes para que un juego o mod cambie en tiempo real:

- Gatillos.
- Luces.
- Hápticos.
- Perfil.
- Vibración.
- Estado de munición, salud, velocidad o terreno.

Incluir SDKs pequeños para:

- C# / Unity.
- C++ / Unreal.
- Python.
- JavaScript.

## 18. Sistema de plugins seguro

Permitir módulos para:

- Nuevos efectos.
- Integraciones con juegos.
- Fuentes de telemetría.
- Acciones de Nexus.
- Importadores de perfiles.

Los plugins deben declarar permisos y ejecutarse aislados cuando sea posible.

## 19. Actualizaciones automáticas

Añadir:

- Canal estable y beta.
- Notas de versión.
- Descarga con hash.
- Firma digital.
- Copia de seguridad antes de actualizar.
- Regreso a la versión anterior.
- Actualizaciones separadas para perfiles oficiales y la app.

## 20. Idiomas reales

Existe `language: es` en configuración, pero la interfaz está escrita directamente en español.

Añadir traducciones mediante archivos externos y comenzar con:

- Español latino.
- Inglés.
- Portugués de Brasil.
- Francés.
- Alemán.
- Japonés.

## 21. Sincronización opcional

- Exportar respaldo completo.
- Sincronización con una carpeta elegida por el usuario.
- OneDrive/Google Drive sin cuenta propia al principio.
- Conflictos resueltos por fecha y copia de seguridad.
- Nunca obligar a usar nube.

---

# Prioridad 3 — Pulido y funciones que dan confianza

## 22. Centro de compatibilidad

Una prueba automática que revise:

- Driver HID.
- ViGEmBus.
- HidHide.
- Steam Input.
- DSX/DS4Windows abiertos.
- Bluetooth.
- Frecuencia de entrada.
- Doble input.
- Vibración de salida.
- Gyro DS4 virtual.
- Permisos y antivirus.

Al final debe dar botones de reparación, no solo mostrar el problema.

## 23. Portátil y perfiles por usuario

- Modo portátil junto al `.exe`.
- Modo instalado en AppData.
- Migrar la carpeta `%APPDATA%/DualSenseController` a una carpeta con nombre Nikaido.
- Importación automática de instalaciones anteriores.

## 24. Batería y cuidado del control

- Aviso configurable de batería baja.
- Tiempo estimado restante.
- Historial de carga.
- Aviso si el control sigue conectado cargando muchas horas.
- Apagado del control desde la bandeja cuando sea técnicamente posible.
- Temporizador de inactividad.

## 25. Overlay de juego

Overlay opcional y ligero con:

- Perfil activo.
- Batería.
- Capa de Nexus.
- Estado de gyro.
- Macro activa.
- Modo de emulación.

Debe poder desactivarse por completo para juegos competitivos.

## 26. Modo de compatibilidad para anti-cheat

Crear presets que desactiven:

- Hooks globales innecesarios.
- Overlay.
- Macros.
- Plugins.
- Telemetría externa.
- Funciones experimentales.

Mostrar exactamente qué está activo para que el usuario no juegue a ciegas.

## 27. Importadores

- Importar perfiles básicos de DS4Windows cuando sea posible.
- Importar/exportar presets de curvas.
- Convertir perfiles JSON antiguos a `.Nika`.
- Asistente visual que explique lo que no se pudo convertir.

## 28. Documentación dentro de la app

- Ayuda contextual.
- Ejemplos animados.
- Presets recomendados.
- Buscador de ajustes.
- Botón “¿Por qué no funciona?” que abra Diagnóstico con el filtro correcto.

---

# Orden recomendado de desarrollo

## Nikaido 2.5 — Base comercial

1. Pruebas físicas y banco de latencia.
2. Arreglo de perfiles automáticos.
3. Feedback de vibración virtual al DualSense.
4. HidHide y asistente de drivers.
5. Separación inicial de `modern_app.py`.
6. Instalador, actualizador y CI.

## Nikaido 2.6 — Edge y multijugador

1. DualSense Edge.
2. Múltiples controles.
3. Touchpad avanzado.
4. KeyBridge 2.0 con Raw Input.
5. Perfiles por dispositivo.

## Nikaido 3.0 — La función que vende la app

1. DualSense virtual.
2. Audio/Haptics Studio.
3. Audio y hápticos por Bluetooth.
4. Modo nativo híbrido.
5. SDK/API para mods.

## Nikaido 3.1 — Ecosistema

1. Nikaido Hub.
2. Plugins.
3. Idiomas.
4. Sincronización.
5. Importador de DS4Windows.

---

# Mi recomendación principal

No intentaría añadir veinte cosas pequeñas primero. La ruta más fuerte es:

1. **Hacer impecable la estabilidad física.**
2. **Añadir feedback de vibración y HidHide.**
3. **Soportar Edge y varios controles.**
4. **Construir DualSense virtual con Audio/Haptics Studio.**
5. **Usar `.Nika` y Nikaido Hub como ecosistema propio.**

Nexus, `.Nika`, Diagnóstico y KeyBridge ya le dan personalidad. El objetivo no debe ser hacer otro DS4Windows con otra skin, sino convertir Nikaido en la herramienta más completa y fácil específicamente para DualSense.
