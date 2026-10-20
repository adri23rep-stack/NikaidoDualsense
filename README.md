# Nikaido DualSense para Windows

Aplicación de escritorio para configurar y personalizar el **PlayStation 5 DualSense** en Windows. La interfaz principal usa Qt/PySide6 y reúne conexión USB/Bluetooth, perfiles, gatillos adaptativos, remapeo, macros, sticks, giroscopio y diagnóstico en vivo.

![Version](https://img.shields.io/badge/version-2.9.8.13-purple)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-blue)
![License](https://img.shields.io/badge/license-Proprietary-red)


## Características

* **Conexión automática**: Detecta si el DualSense esta conectado por USB o Bluetooth automáticamente
* **Adaptive Trigger Studio**: Biblioteca de 18 sensaciones, monitor físico, prueba real, copiar/vincular L2-R2, resistencia, vibración, zonas, frecuencia y curvas
* **Curva Multizona Real**: Cuatro tramos editables convertidos a las 10 zonas físicas de resistencia del DualSense
* **Touchpad como Mouse**: Movimiento relativo del cursor, clic izquierdo y sensibilidad configurable
* **Botón MIC y mute global**: Controla un micrófono, todos los activos o todos excepto el DualSense; en modo global emula la tecla física de mute del micrófono de Windows, refuerza el cambio en cada entrada y sincroniza el LED naranja
* **Vibración real del juego**: Convierte el feedback del Xbox 360/DS4 virtual en vibración física del DualSense con fuerza, balance, suavizado y apagado de seguridad
* **Perfiles automáticos 2.0**: Detecta la ventana activa, usa prioridades, ruta/título opcionales y restaura el perfil anterior al salir del juego
* **Compatibilidad HidHide**: Detecta riesgo de doble entrada, revisa lista permitida y dispositivos ocultos y abre las herramientas oficiales sin cambios agresivos
* **Gyro Aim y Flick Stick**: Mouse, stick derecho o passthrough DS4; activadores, presets, respuesta por eje y giro direccional con la palanca
* **Mouse → Giroscopio DS4**: Fuente opcional para controlar el sensor virtual con el mouse, apagada por defecto y configurable por perfil
* **Nikaido Input Studio**: Deadzones, anti-deadzone, curvas visuales funcionales, sensibilidad X/Y, inversión y drift por perfil con vista física/virtual en vivo
* **Perfiles Completos**: 8 perfiles comunitarios no oficiales para distintos géneros y perfiles personales con icono y banner independientes, gatillos L2/R2, vibración, luces, macros, audio e Input Studio
* **RGB Studio**: Vista previa animada, paletas, efectos y modos Prioridad Nikaido, Equilibrio o Prioridad del juego para evitar que dos salidas peleen sin control
* **Macros Avanzadas**: Editor visual de botones, combos, palancas y gatillos; tiempos por acción, grabación analógica, activadores por botón/combo/palanca/L2-R2, plantillas y asignación por perfil
* **Nikaido Nexus**: Editor visual del DualSense con inspector por botón, capas, validación, búsqueda, historial deshacer/rehacer, copiar/pegar, teclado, mouse, macros, gyro, turbo y gestos avanzados
* **Centro de diagnóstico**: Frecuencia física HID, procesamiento de Nikaido, ViGEm, latencia promedio/p95, pulsaciones, fallos reales, conflictos, capturas y reportes sanitizados
* **Monitor de Batería**: Muestra porcentaje y estado de carga; opcionalmente usa las luces blancas del jugador como indicador físico de cuatro niveles
* **Apariencia Studio**: Fondos optimizados, encuadre y posición, viñeta, transparencias, cinco presets, cinco acentos, densidad compacta y reducción de movimiento
* **Nikaido, asistente visual**: Mascota oficial integrada al wizard y al programa con poses, diálogos contextuales y consejos ocasionales
* **Asistente de bienvenida**: Recorrido inicial por conexión, perfiles, Nexus, gyro, macros y apariencia con estado del control en vivo; puede repetirse desde Ajustes
* **17 secciones integradas**: Dashboard, perfiles, perfiles automáticos, Diagnóstico, Nikaido Nexus, Input Studio, Gyro Studio, macros, luces, vibración, gatillos adaptativos, audio, emulación, calibración, herramientas, compatibilidad y ajustes
* **Bandeja inteligente**: al minimizar, Nikaido permanece junto al reloj con un icono que muestra conexión, carga y nivel de batería; cerrar siempre termina el proceso
* **Formato oficial `.Nika`**: Importación y exportación completa de perfiles, iconos, banners, macros, luces, gatillos e Input Studio; los perfiles JSON anteriores siguen siendo compatibles
* **Guardado seguro**: Escritura atómica con reintentos, indicador de estado, respaldos automáticos y recuperación cuando un archivo se daña
* **Reparación Bluetooth segura**: refresca únicamente el DualSense y reinicia el servicio sin borrar emparejamientos de audífonos, teclados u otros dispositivos
* **Empaquetado**: Se puede convertir a un solo archivo .exe ejecutable


## Versión 2.9.8.13 Beta 1 — Emulation & Integration Hub

- Rediseña la pestaña de Emulación como un centro visual con selector de DualSense nativo, DualShock 4, Xbox 360 y KeyBridge.
- Añade una vista vectorial dinámica del control: emblema central, iluminación y botones cambian según la salida elegida.
- Integra controles rápidos de emulación, reconexión, HidHide, vibración, touchpad como mouse y giroscopio.
- Conserva el editor completo de KeyBridge plegado y accesible desde la misma pantalla.
- Añade estado en vivo de conexión, batería, perfil, dispositivo virtual y latencia interna.
- Incluye pruebas rápidas de entrada, vibración, reinicio virtual y modo pánico.
- Mantiene Low Profile y la bomba HID de baja latencia sin modificaciones.

> La apariencia y la operación final deben validarse en Windows con PySide6, ViGEmBus y un DualSense físico.

## Versión 2.9.8.12 Beta 1 — Low Profile Prototype

- Al minimizar, puede destruir por completo la ventana Qt y conservar únicamente motores y bandeja.
- La interfaz se reconstruye desde cero al abrir Nikaido desde el icono.
- Mantiene conexión, emulación, perfil activo, macros, gyro y HID Pump sin reiniciarlos.
- Detiene timers visuales, desconecta callbacks de la GUI y libera widgets, pixmaps y ciclos Python.
- Añade el ajuste **Activar Low Profile al minimizar**, habilitado en esta versión de prueba.
- El menú de bandeja muestra el estado Low Profile, permite abrir Nikaido y cambiar perfil.

> Validación física pendiente: el ahorro real de RAM/CPU debe medirse en Windows durante una sesión de juego.

## Versión 2.9.8.11 Beta 1 — Low-Latency HID Pump

- Sustituye el ciclo interno de pydualsense que mezclaba una lectura física con una escritura de luces/rumble en cada paquete.
- Publica el informe HID crudo apenas llega, sin decodificación por eventos ni copias profundas dentro de la librería externa.
- Mueve luces, vibración, micrófono y gatillos físicos a un hilo separado de 60 Hz; solo escribe cuando la salida cambia o vence un keepalive.
- Despierta el pipeline virtual mediante un evento por paquete nuevo en lugar de esperar exclusivamente al sondeo de 1 ms.
- Conserva la ruta anterior como fallback cuando el backend no permite instalar la bomba de baja latencia.
- Añade diagnóstico de reportes recibidos, escrituras físicas agrupadas, omisiones y errores de la bomba HID.

## Versión 2.9.8.10 Beta 1 — Input Latency Hotfix

- Detección del contador HID a 1 kHz únicamente mientras la emulación está activa.
- Procesamiento completo por paquete nuevo, con heartbeat de 250 Hz para macros temporizadas.
- Resolución de temporizador de 1 ms en Windows, restaurada al cerrar Nikaido.
- Prioridad moderada para el hilo de entrada; no usa prioridad de tiempo real.
- Lectura del control separada de escrituras RGB, vibración, micrófono y gatillos.
- Neutralización protegida para impedir que una desconexión reinyecte un estado viejo en ViGEm.
- Nuevas métricas de diagnóstico para confirmar tasa, latencia y estado del modo rápido.

## Versión 2.9.8.9 Beta 1

Stability & Lifecycle Audit:

- Corrige la retención de ventanas, callbacks y timers Qt entre ciclos consecutivos de inicio y cierre.
- Profile Studio contiene y registra las excepciones de sus botones, conserva el flujo real de creación/edición y libera sus diálogos.
- El cierre guarda cada subsistema de forma independiente; un exportador defectuoso ya no impide persistir los demás ajustes.
- Los fallos de arranque de la interfaz devuelven un código de error real y no se presentan como una ejecución exitosa.
- El launcher, el instalador y la herramienta de reparación separan la validación de dependencias de la importación del código de Nikaido.
- La bandeja es opcional y puede desactivarse limpiamente si su backend no carga, sin romper importaciones del núcleo.
- Se añadieron regresiones de ciclo de vida, tres ciclos Qt, Profile Studio, perfiles incluidos, recursos visuales dañados y persistencia parcial.

No se afirma prueba física con DualSense, ejecución en Windows ni compilación del instalador en Windows en esta revisión.

## Versión 2.9.8.8 Beta 1

Dashboard Startup Fallback Hotfix:

- Corrige el `NameError` de `fallback_glyph` que podía cerrar la interfaz al reconstruir el Dashboard en un segundo arranque.
- El Dashboard importa el generador de iconos desde `gui.profile_visuals`, su módulo dueño.
- Los perfiles sin icono personalizado, con icono temático o con una ruta de imagen inexistente muestran un fallback seguro.
- Se añadió una regresión Qt que ejecuta dos actualizaciones consecutivas del icono del perfil, reproduciendo el escenario reportado.
- No se modificaron los perfiles, banners, configuraciones ni el Estilo A introducido en 2.9.8.7.

No se afirma prueba física con DualSense ni compilación del instalador en Windows en esta revisión.

## Versión 2.9.8.7 Beta 1

Profile Visual Identity & Style A:

- Las tarjetas adoptan el **Estilo A · Sobrio premium**: el borde permanece estable y la selección se comunica mediante fondo ligeramente elevado y sombra suave.
- La sombra solo se procesa para la tarjeta seleccionada o bajo el mouse; las demás tarjetas no mantienen efectos gráficos activos.
- Icono y banner ahora son recursos independientes y editables desde la pestaña General del perfil.
- Los perfiles incluidos pueden restaurar su icono vectorial y banner original de Team Nikaido.
- Los perfiles personales copian, eliminan, importan y exportan ambos recursos por separado.
- Los paquetes `.Nika` nuevos incluyen `icon_file` y `banner_file`, manteniendo `image_file` para compatibilidad con lectores anteriores.
- Los paquetes antiguos con una sola imagen se migran a dos archivos físicos independientes para evitar que editar el icono cambie el banner.
- Se ejecutaron pruebas Qt reales en modo `offscreen` para creación, edición, sombreado y persistencia visual.

No se afirma prueba física con DualSense ni compilación del instalador en Windows en esta revisión.

## Versión 2.9.8.6 Beta 1

Profile Editor Actions Hotfix:

- Corrige el fallo silencioso que impedía abrir **Editar perfil** y **Nuevo perfil**: el editor usaba el helper visual `label(...)` sin importarlo.
- Crear un perfil ya no depende de que exista un perfil aplicado. Si el DualSense todavía no está conectado, usa el perfil seleccionado o el perfil base de Nikaido.
- Si por alguna razón no existe un perfil base válido, la interfaz muestra un error claro en lugar de ignorar el clic.
- Se ejecutaron pruebas Qt reales en modo `offscreen`: construcción y guardado de los ocho perfiles incluidos, creación desde el botón superior y edición desde el panel lateral.
- Se agregaron regresiones automáticas para cubrir el flujo completo de ambos botones.

No se afirma prueba física con DualSense ni compilación del instalador en Windows en esta revisión.

## Versión 2.9.8.5 Beta 1

Profile Gallery Startup Hotfix:

- Corrige el `ImportError` que impedía iniciar Nikaido después de separar el editor y la galería de perfiles.
- `ProfileEditorDialog` y `profile_image_widget` ahora se importan desde su módulo dueño y siguen disponibles mediante la ruta histórica para compatibilidad.
- El inicio seguro verifica primero dependencias y después el código de Nikaido. Un error del proyecto ya no provoca una reinstalación inútil de PySide6, pycaw o comtypes.
- El instalador aplica la misma separación y muestra un error claro cuando las dependencias están bien pero el código no puede importarse.
- Se agregaron pruebas de regresión para validar los exports públicos del facade y los scripts de arranque.

No se afirma prueba física ni compilación Windows en esta revisión.

## Versión 2.9.8.4 Beta 1

Game Profile Gallery:

- Profile Studio adopta la galería moderna aprobada: portadas originales, filtros, vista de cuadrícula/lista y panel lateral por módulos.
- Se incluyen ocho configuraciones comunitarias no oficiales para Warzone, Forza Horizon 5, Resident Evil 4, Elden Ring, EA Sports FC, Street Fighter 6, Minecraft y Ghost of Tsushima.
- Los perfiles incluidos usan arte abstracto original de Team Nikaido; no contienen portadas, logotipos ni archivos de publishers.
- RGB Studio, Gatillos Adaptativos, Vibración, Macros e Input Studio se abren directamente desde el panel de detalle.
- La biblioteca, la presentación y la migración viven en módulos separados de la interfaz.
- Los IDs históricos siguen siendo compatibles; aliases antiguos se migran sin duplicar favoritos, reglas por juego o macros.
- La galería no tiene animaciones continuas ni temporizadores por tarjeta. Solo reconstruye cuando cambian datos, filtros o columnas.
- Los perfiles incluidos pueden editarse y restaurarse; los personales pueden duplicarse, importarse, exportarse y eliminarse.
- Validación automatizada incluida en `docs/history/validations/VALIDACION_2.9.8.4.md`.

No se afirma prueba física ni compilación Windows en esta revisión.

## Versión 2.9.8.3 Beta 1

Profile Studio Lite:

- Rediseño visual más limpio y compacto, conservando la vista híbrida con panel lateral.
- Se elimina el repintado continuo de todas las tarjetas y los previews RGB por perfil.
- Seleccionar una tarjeta actualiza solo su estado y el panel de detalle; ya no reconstruye toda la galería.
- Búsqueda con espera breve, resize agrupado y reconstrucción únicamente cuando cambian filtros, perfiles o columnas.
- Tarjetas con menos adornos, dos acciones principales y resumen directo de L2, R2 e iluminación.
- Avatares planos sin halos, arcos giratorios ni efectos pesados; las imágenes personalizadas siguen teniendo prioridad.
- El editor conserva su preview, pero funciona a una frecuencia reducida.
- Validación automatizada completa incluida en `docs/history/validations/VALIDACION_2.9.8.3.md`.

No se afirma prueba física ni compilación Windows en esta revisión.

## Versión 2.9.8.2 Beta 1

Profile Studio 2.0 antes de 3.0:

- Hotfix: corrige el bloqueo que impedía abrir la pestaña Perfiles por una clave de color inválida.
- Vista híbrida con tarjetas animadas, búsqueda, categorías, favoritos, ordenamiento y panel lateral completo.
- Iconos vectoriales escalables con temas propios; las imágenes personalizadas siguen teniendo prioridad.
- Un único reloj compartido anima todos los avatares y previews RGB, respetando Reducir movimiento.
- Editor de perfiles pulido con descripción multilínea, categorías sugeridas y galería de estilos visuales.
- Los perfiles de fábrica se reconstruyeron usando los presets de Trigger Studio y conservan sus IDs históricos.
- Se añaden Conducción precisa y Horror inmersivo sin romper perfiles, favoritos ni reglas por juego anteriores.
- Duplicado más seguro, limpieza de recursos si falla, eliminación contextual y accesos rápidos a RGB Studio y Gatillos.
- Validación automatizada: 463 pruebas aprobadas y 2 omitidas por ausencia de PySide6 en el entorno de revisión.

No se afirma prueba física ni compilación Windows en esta revisión. Consulta `docs/history/releases/RELEASE_2.9.8.2.md`.


## Versión 2.9.8.0 Beta 1

Pulido de hardware antes de 3.0:

- Las luces blancas del jugador pueden mostrar cuatro niveles de batería, carga progresiva y parpadeo crítico, o conservar número de jugador, control del juego y apagado.
- RGB Studio añade Prioridad Nikaido, Equilibrio y Prioridad del juego. Un color fijo puede reafirmarse para recuperar el control o Nikaido puede dejar de escribir por completo.
- Adaptive Trigger Studio estrena 18 presets organizados, monitor físico L2/R2, prueba real, copia, limpieza y vinculación completa.
- Los gatillos viven en un módulo separado para conservar la interfaz mantenible.
- Se protege el estado de batería desconocida, se reintentan escrituras RGB fallidas y se conserva la compatibilidad con perfiles anteriores.
- Validación automatizada: 453 pruebas aprobadas y 2 omitidas por ausencia de PySide6 en el entorno de revisión.

No se afirma prueba física ni compilación Windows en esta revisión. Consulta `docs/history/releases/RELEASE_2.9.8.0.md`.


## Versión 2.9.7.0 Beta 1

Preparación para la primera beta pública:

- La prueba manual de vibración usa la misma ruta segura en desarrollo y en el ejecutable compilado. Durante la prueba, el feedback del control virtual no puede apagar los motores y la salida se reafirma hasta finalizar.
- El asistente incluye más de treinta consejos mezclados sin repetirse hasta terminar la bolsa. El aviso usa un sonido corto y opcional que puede apagarse desde Ajustes.
- Se añadió un actualizador para la edición independiente: consulta un manifiesto HTTPS, compara versiones, descarga el instalador, verifica tamaño y SHA-256 y lo instala sobre la versión actual sin borrar perfiles ni ajustes.
- El instalador conserva el mismo AppId, cierra Nikaido de forma controlada y limpia archivos internos obsoletos antes de copiar la versión nueva.
- Ajustes muestra la versión, canal estable/beta, búsqueda manual, progreso de descarga y estado del actualizador.
- Diagnóstico ahora permite copiar un resumen seguro directamente al portapapeles.
- Todos los metadatos, documentos, instaladores y scripts públicos usan únicamente **Team Nikaido**. La aplicación permanece sin firma digital por el momento.
- El proceso de compilación usa **Privacy Auditor 2.0**: bloquea datos del equipo actual y rutas dentro de archivos propios, pero registra como aviso los metadatos históricos de compiladores externos incluidos en DLL legítimas. Cada ZIP incorpora un reporte seguro con valores ocultos.
- Se conservan las mejoras de ruta corta para PySide6 y las métricas reales del monitor incluidas en 2.9.6.4.

El servidor público del actualizador debe configurarse al publicar la primera release; el motor queda inactivo de forma segura mientras la URL esté vacía. Consulta `docs/UPDATES.md` y `docs/PRIVACY_AUDITOR_2.md`.

Consulta `docs/history/releases/RELEASE_2.9.7.0.md`.

## Versión 2.9.6.3

Hotfix del botón MIC:

- Cuando el alcance es **Todos los micrófonos activos**, pulsar el botón MIC del DualSense envía a Windows `APPCOMMAND_MICROPHONE_VOLUME_MUTE`, la misma orden de una tecla física para silenciar el micrófono.
- Nikaido conserva el control directo de Core Audio como refuerzo para aplicar el mismo estado a todos los endpoints, no solo al predeterminado.
- El estado original se guarda antes de enviar la orden de teclado, evitando que la restauración deje un micrófono atorado.
- El LED MIC naranja responde inmediatamente y después se confirma con el estado real de Windows.
- El botón de la interfaz y los comandos internos continúan usando el método directo para no generar pulsaciones de teclado inesperadas.

Consulta `docs/history/releases/RELEASE_2.9.6.3.md`.

## Versión 2.9.6.2

Hotfix para Windows:

- La compilación permite el `Nikaido.exe` real en HidHide y elimina la entrada rota a `python.exe` de la misma carpeta.
- Activar el ocultamiento primero registra Nikaido, evitando que el programa pierda acceso al DualSense.
- Se corrigió la lectura de las salidas reales de `HidHideCLI`, incluido el JSON de dispositivos.
- Se aceptan IDs Bluetooth `BTHENUM` y `BTHLEDEVICE`.
- El mute de micrófono conserva los reintentos y la verificación añadidos en 2.9.6.1.
- Se mantiene `DIAGNOSTICAR_AUDIO_HIDHIDE.bat` para generar un reporte de solo lectura.

Consulta `docs/history/releases/RELEASE_2.9.6.2.md`.

## Versión 2.9.6

* **Mute global real:** el botón MIC puede silenciar todos los micrófonos activos de Windows.
* **Excepto DualSense:** mantiene activo el micrófono integrado del control y usa únicamente su LED naranja como indicador.
* **Restauración inteligente:** recuerda qué entradas ya estaban silenciadas y restaura cada una sin activar dispositivos que estaban apagados.
* **Hotplug protegido:** un micrófono conectado o reactivado durante la sesión global también queda silenciado y se incorpora a la restauración.
* **Perfiles `.Nika`:** cada perfil guarda el alcance `específico`, `todos` o `todos excepto DualSense`.
* **Cambios seguros de perfil:** una sesión global activa se restaura antes de cambiar de alcance, evitando estados atorados.

Consulta `docs/history/releases/RELEASE_2.9.6.md`.

## Hotfix 2.9.5.3

* **Inicio seguro:** `INICIAR_NIKAIDO.bat` usa siempre el Python de `.venv`, comprueba `comtypes`/`pycaw` y repara el entorno si quedó incompleto.
* **Doble clic protegido:** si `main.py` se abre con el Python global, Nikaido se reinicia automáticamente con `.venv\Scripts\python.exe`.
* **Reparación real de audio:** el reparador reinstala Core Audio sin caché y muestra las rutas exactas de Python y `comtypes`.
* **Diagnóstico claro:** los errores de audio indican qué intérprete abrió Nikaido en lugar de repetir solamente “ejecuta install.bat”.

Abre la distribución de código fuente con `INICIAR_NIKAIDO.bat`. Consulta `docs/history/releases/RELEASE_2.9.5.3.md`.

## Hotfix 2.9.5.2

- Corrige el rango imposible `pycaw>=20251023,<2027`, que impedía instalar el soporte de micrófono en cualquier versión de Python.
- Fija `pycaw==20251023`, la versión usada por el motor de audio de Nikaido.
- Añade una prueba que comprueba que cada rango de dependencias acepta su versión mínima o exacta.
- Conserva la reparación de GUI, la dependencia explícita de `comtypes` y `REPARAR_GUI_Y_AUDIO.bat` de la 2.9.5.1.

Consulta `docs/history/releases/RELEASE_2.9.5.2.md`.

## Versión 2.9.5

Nikaido 2.9.5 convierte la sección Audio en una función real:

* **Botón MIC → Windows:** una pulsación silencia o reactiva el micrófono seleccionado sin bloquear la lectura del control.
* **LED naranja sincronizado:** el DualSense refleja el mute hecho desde Nikaido o desde Windows.
* **Micrófono por perfil:** cada `.Nika` puede conservar dispositivo, volumen opcional y estado al aplicar el perfil.
* **Fallback seguro:** si unos audífonos o micrófono guardado están desconectados, usa temporalmente el predeterminado sin borrar la selección.
* **Página Audio completa:** selector de entrada, volumen, mute, actualización de dispositivos y acceso a la configuración de sonido.
* **Build actualizado:** PyInstaller y el build protegido incluyen `pycaw` y `comtypes`, con auto-prueba de importación.

Consulta `docs/history/releases/RELEASE_2.9.5.md`.

## Versión 2.9

Nikaido 2.9 corrige la curva visual de Input Studio y estrena idiomas configurables:

* **Curva visual reparada:** Lineal, Exponencial y Agresiva ahora cambian el gráfico al instante y coinciden con el procesamiento real.
* **Curva personalizada:** El editor permanece visible y los puntos se pueden arrastrar al seleccionar Personalizada.
* **Tres idiomas:** Español, English y Português (Brasil).
* **Selector en vivo:** El idioma puede elegirse desde el wizard o Ajustes sin reiniciar la aplicación.
* **Interfaz traducible:** Navegación, páginas bajo demanda, menús, asistente, Dashboard, Input Studio y mensajes principales se actualizan conservando el estado.
* **Primer inicio imposible de perder:** el idioma ocupa la primera pantalla completa y debe elegirse antes de continuar u omitir el recorrido.
* **Batería honesta:** mientras el DualSense todavía no entrega una lectura, Nikaido muestra “—” o “Leyendo…” en lugar de un 0 % falso.
* **Dashboard corregido:** el medidor de batería usa una tarjeta amplia, barra de carga y estados legibles incluso en ventanas estrechas.
* **Raíz ordenada:** reportes, hotfixes, notas y validaciones históricas viven en `docs/history/`; los `.bat` quedan fáciles de encontrar.

La auditoría de estabilidad anterior está documentada en `docs/history/releases/RELEASE_2.9.4.md`.

## Versión 2.7

Nikaido 2.7 presenta a la mascota oficial dentro del programa:

* **Wizard acompañado:** Nikaido permanece visible durante los seis pasos con una pose y explicación diferente.
* **Conexión en vivo:** el asistente muestra USB/Bluetooth, batería y cambia de reacción cuando encuentra el DualSense.
* **Componente reutilizable:** el panel de mascota y sus 20 sprites quedan preparados para Dashboard, avisos y consejos futuros.
* **Arte optimizado:** sprites transparentes normalizados para Qt y empaquetados automáticamente con PyInstaller.
* **Recorrido renovado:** más espacio, jerarquía visual clara y acceso manual para buscar el control.
* **RAM optimizada:** el wizard se destruye al cerrar, las imágenes se decodifican al tamaño visible, las páginas se importan bajo demanda y el historial de diagnóstico ya no procesa cada tick HID.

Consulta `docs/history/releases/RELEASE_2.7.2.md`.


## Versión 2.6

Nikaido 2.6 reorganiza la interfaz estable sin cambiar su funcionamiento:

* **Arquitectura modular:** `modern_app.py` ahora es una fachada pequeña y las pantallas viven por dominio en `gui/pages`.
* **Ventana coordinadora separada:** navegación, estado y conexión entre motores viven en `gui/main_window.py`.
* **Compatibilidad conservada:** `main.py`, plugins e imports antiguos pueden seguir usando `gui.modern_app`.
* **Build protegido:** PyInstaller incluye explícitamente todos los módulos Qt nuevos.
* **Pruebas adaptadas:** las regresiones inspeccionan toda la interfaz modular y evitan que el archivo monolítico vuelva a crecer.

Consulta `docs/history/releases/RELEASE_2.6.1.md` y `docs/ARCHITECTURE_260.md`.


## Versión 2.5

La versión 2.5 fortalece la base necesaria para competir con herramientas maduras de emulación:

* **Feedback virtual → DualSense:** el rumble del juego regresa al control físico sin escribir al HID dentro del callback de ViGEm.
* **Perfiles automáticos 2.0:** reglas por ventana/proceso con prioridad, retrasos, restauración y respeto a cambios manuales.
* **Centro de compatibilidad:** revisión guiada de HidHide y doble entrada, con selección explícita de dispositivos.
* **Diagnóstico ampliado:** reporta feedback, automatización e HidHide dentro de los paquetes de soporte.
* **Distribución más seria:** instalador opcional con Inno Setup, licencia, CI para Windows y auto-prueba de la nueva ruta.
* **Mouse listo para jugar:** Mouse → Stick y Mouse → Gyro muestran una cuenta visible de 5 segundos solo al encenderse desde Nikaido; después Ctrl + M libera o reactiva el mouse al instante. El aviso flotante no recibe foco ni bloquea clics.
* **Seguridad 2.5.6:** importadores limitados contra rutas ZIP peligrosas, bombas de compresión, JSON abusivo, macros gigantes, imágenes pesadas y herramientas externas suplantadas; instalador normal sin privilegios de administrador.

Consulta `docs/history/releases/RELEASE_2.5.0.md`, `docs/history/hotfixes/HOTFIX_2.5.1.md`, `docs/history/hotfixes/HOTFIX_2.5.2.md`, `docs/history/hotfixes/HOTFIX_2.5.3.md`, `docs/history/hotfixes/HOTFIX_2.5.4.md`, `docs/history/hotfixes/HOTFIX_2.5.5.md`, `docs/history/hotfixes/HOTFIX_2.5.6.md`, `SECURITY.md`, `docs/VIRTUAL_FEEDBACK.md`, `docs/AUTO_PROFILES_250.md` y `docs/HIDHIDE_250.md`.


## Versión 2.3

La versión 2.3 es una pasada completa de calidad comercial sobre todo lo existente:

* **Nexus más serio:** deshacer/rehacer, copiar/pegar, orden de acciones, búsqueda, validación de destinos, administración completa de capas, entradas físicas iluminadas en vivo y navegación por teclado.
* **Apariencia Studio:** presets Nikaido, Cristal, Enfoque, AMOLED y Minimal; cinco colores de acento; encuadre cover/contain/stretch; posición, viñeta, zoom real hasta 180 %, densidad y reducción de movimiento.
* **Arranque más rápido:** Dashboard inmediato y carga diferida de las pantallas pesadas. Si una sección falla, queda aislada y puede reintentarse sin tumbar la conexión del control.
* **Perfiles `.Nika` endurecidos:** importación transaccional, límites contra archivos abusivos, imágenes verificadas, referencias de macros remapeadas y exportación de dependencias usadas por Nexus.
* **Estabilidad:** una sola instancia, reportes locales de fallos del hilo principal y workers, errores visibles en el `.exe`, cierre seguro incluso después de una inicialización parcial y guardados resistentes a bloqueos breves de antivirus.
* **Compilación:** metadatos de Windows, manifiesto SHA-256, validación de HID, Python y `qwindows.dll` antes de aceptar una distribución.
* **2.3.2:** bandeja inteligente con icono dinámico de batería, carga, conexión, perfil activo, clic izquierdo para restaurar y menú rápido.
* **2.3.1:** cerrar ahora finaliza el proceso de verdad, minimizar conserva la bandeja opcional y el nuevo asistente de bienvenida presenta las funciones y ajustes principales.

Consulta `docs/history/releases/RELEASE_2.3.2.md`, `docs/history/releases/RELEASE_2.3.1.md`, `docs/TRAY_BATTERY.md`, `docs/ONBOARDING.md`, `docs/NEXUS.md` y `docs/APPEARANCE.md`.


## Versión 2.2

Esta versión añade dos sistemas construidos sobre la arquitectura existente:

* **Nikaido Nexus:** espacio visual para seleccionar botones directamente en un DualSense dibujado, revisar sus acciones, crear reglas rápidas y navegar las capas mediante Nexus Flow.
* **Personalización visual:** fondo elegido por el usuario, copia segura a AppData, oscurecimiento, zoom y transparencia en vivo de paneles, barra lateral y botones.

Nexus reutiliza el mapper avanzado y los perfiles `.Nika`; no crea un segundo motor ni duplica bindings. Consulta `docs/history/releases/RELEASE_2.2.0.md`, `docs/NEXUS.md` y `docs/APPEARANCE.md`.


## Versión 2.1

Esta versión convierte tres áreas prioritarias en sistemas completos:

* **Diagnóstico profesional:** separa la frecuencia física del DualSense, el procesamiento de Nikaido y ViGEm; mide latencia promedio/p95/máxima, pulsaciones, fallos reales, conflictos, captura de sesiones y reporte ZIP sin datos personales.
* **Mapper avanzado por perfil:** editor de capas y gestos con acciones al presionar, mantener, soltar, corto, largo, doble exclusiva y alternar; combina control virtual, teclado, mouse, macros, perfiles, capas y acciones de gyro.
* **Gyro Aim avanzado:** presets, activación con cualquier botón, respuesta fina por eje y Flick Stick para salida de mouse o stick derecho.

La configuración 2.0, los perfiles antiguos y el formato `.Nika` versión 1 siguen siendo compatibles. El mapa avanzado global anterior se conserva como respaldo para perfiles que aún no tengan reglas propias. Consulta `docs/history/roadmaps/ROADMAP_2.1.md`, `docs/history/releases/RELEASE_2.1.0.md` y `docs/history/hotfixes/HOTFIX_2.1.1.md` para el detalle.


## Hotfix 2.1.1

- Corrige las alertas falsas de paquetes perdidos: los saltos normales del contador Sony ahora se registran como informes intermedios reemplazados.
- Separa **HID físico**, **procesamiento de Nikaido**, **estados nuevos observados** y **control virtual**.
- Calcula la frecuencia física usando el avance real del contador HID, incluso cuando Nikaido conserva solamente el estado más reciente.
- La frecuencia de Gyro Engine se basa en secuencias nuevas y ya no puede mostrar valores imposibles por callbacks agrupados.
- Añade latencia promedio/p95 específica para pulsaciones y liberaciones.
- Los reportes incluyen estado físico, estado virtual y desglose temporal de cada muestra.
- La ausencia de calibración permanente en passthrough DS4 es ahora un aviso informativo, no un fallo de salud.

## Hotfix 2.0.4

- El estado de botones, palancas, gatillos y sensores se toma ahora de una sola copia completa del reporte HID, evitando mezclar partes de paquetes distintos.
- Corrige la latencia de botones del control emulado y mantiene la ruta de ViGEm separada de la actualización visual.
- Corrige el orden real de la IMU del DualSense: primero giroscopio y después acelerómetro.
- Las calibraciones anteriores de gyro se conservan, pero no se consideran confiables hasta recalibrar con esta versión.
- El mapper ignora botones sin bindings y Macros deja de reconstruir toda su biblioteca en cada paquete HID.
- Añade Mouse → Giroscopio virtual como opción apagada por defecto, con sensibilidad, inversión y mezcla con el movimiento físico.

## Hotfix 2.0.3

- Corrige la mezcla lateral que podía aparecer al mover el giroscopio arriba o abajo en passthrough DS4.
- El centro automático se captura una sola vez al activar y queda congelado durante la sesión.
- Calibra pitch, yaw y roll por separado para que un eje en movimiento no contamine los demás.
- Usa el acelerómetro para evitar tomar una inclinación como posición de reposo.
- Respeta siempre la calibración guardada en el perfil `.Nika` y filtra únicamente la fuga mínima entre ejes.

## Hotfix 2.0.2

- Corrige la barra lateral real que aparecía gris en Windows; el fondo ahora se fuerza al tema oscuro.
- Amplía la barra lateral y separa título/subtítulo para que ninguna opción quede cortada.
- Evita que el centrado automático del passthrough DS4 aprenda un movimiento real como drift.
- Suprime el giro contrario mientras el sensor confirma un nuevo centro de reposo.
- Endurece la zona de ruido sin alterar los signos ni la respuesta de los tres ejes.

## Hotfix 2.0.1

- Corrige giro fantasma en el passthrough DS4 mediante calibración y centrado de reposo.
- Reduce la latencia de las palancas emuladas y mantiene el ciclo de entrada a 120 Hz reales.
- Renueva el diseño de pestañas y evita que sus títulos se recorten.
- Muestra en vivo las acciones mientras se graba una macro.

## Versión 2.0

Esta revisión mantiene las funciones existentes y se concentra en calidad y estabilidad:

* navegación lateral desplazable y organizada por áreas;
* avisos no modales, tooltips y estados visuales consistentes;
* guardado agrupado para evitar escrituras por cada movimiento de un control;
* calibración guiada con validación, progreso y restauración segura;
* actualización en vivo limitada a la pantalla visible;
* perfiles `.Nika` con límites, respaldos y recuperación de datos;
* cierre seguro de hilos, bandeja y motores aunque un módulo falle;
* compatibilidad con perfiles, macros y ajustes anteriores.

## Requisitos

* Windows 10 o Windows 11
* Python 3.10 o superior (solo para desarrollo)
* DualSense conectado via USB o Bluetooth

## Instalación rápida

### Opción 1: Desde código fuente

1. **Clona o descarga** este repositorio.
2. Ejecuta `install.bat`; no necesita permisos de administrador.
3. Abre siempre `INICIAR_NIKAIDO.bat`. Este archivo usa el runtime corto de `%LOCALAPPDATA%\NKB\rt` y repara GUI/audio si detecta que falta algún paquete.

```cmd
install.bat
INICIAR_NIKAIDO.bat
```

También puedes abrir `main.py`: cambiará automáticamente al runtime corto cuando ya esté instalado. El iniciador `.bat` sigue siendo la opción recomendada porque también puede crear o reparar una instalación incompleta.

### Opción 2: Ejecutable `.exe`

1. Después de instalar dependencias, ejecuta:

```cmd
COMPILAR_NIKAIDO.bat
```

2. Abre únicamente `release\Nikaido\Nikaido.exe` o `release\ABRIR_NIKAIDO.bat`.
3. El compilador valida el backend HID, el runtime de Python y Qt antes de aceptar la salida.
4. Para crear además un instalador tradicional, instala Inno Setup 6 y ejecuta `CREAR_INSTALADOR.bat` o `python build.py --installer`.
5. Para generar un solo archivo desde consola:

```cmd
python build.py --onefile
```

No ejecutes copias dentro de `build`, `dist` o `.nikaido_build`: son temporales y pueden estar incompletas.

## Uso

#### Interfaz gráfica (por defecto)

```cmd
INICIAR_NIKAIDO.bat
```

### Opciones de línea de comandos

```cmd
INICIAR_NIKAIDO.bat --help

Opciones:
  -m, --minimized    Inicia minimizado a la bandeja del sistema
  -c, --no-gui       Modo consola (sin interfaz grafica)
  -p, --profile      Aplica un perfil al conectar (ej: --profile sniper)
  --reset-bt         Reinicia el Bluetooth al inicio
  -d, --debug        Modo debug con logging verboso
```

### Controles en modo consola

Cuando ejecutas con `--no-gui`, puedes usar estos comandos:

```
dualsense> connect        - Intentar conectar el control
dualsense> disconnect     - Desconectar el control
dualsense> status         - Mostrar estado actual
dualsense> battery        - Nivel de batería
dualsense> profiles       - Listar perfiles disponibles
dualsense> apply sniper   - Aplicar perfil de francotirador
dualsense> reset-bt       - Reiniciar Bluetooth
dualsense> led 255 0 0    - Cambiar LED a rojo
dualsense> exit           - Salir
```

## Perfiles incluidos

|Perfil|Categoria|Descripción|
|-|-|-|
|**Shooter equilibrado**|Shooter|Apuntado cómodo y disparo automático definido|
|**Precisión táctica**|Precisión|Estabilización firme y quiebre pesado al final|
|**Arquería dinámica**|Aventura|Tensión progresiva para arcos y poderes cargados|
|**Respuesta rápida**|Acción|L2 libre y punto de disparo corto en R2|
|**Impacto pesado**|Shooter|Resistencia y retroceso para ataques fuertes|
|**Cadencia alta**|Shooter|Sensación ligera para disparo continuo|
|**Potencia sostenida**|Shooter|Mayor peso para maquinaria y armas pesadas|
|**Conducción precisa**|Conducción|Freno y acelerador progresivos|
|**Horror inmersivo**|Inmersión|Tensión, vibración profunda y RGB tipo latido|
|**Control libre**|General|Sin gatillos adaptativos, vibración ni macros|

## Estructura del proyecto

```text
Nikaido_DualSense/
├── main.py                       # Arranque, servicios y cierre seguro
├── nikaido_version.py            # Versión única de app, configuración y .Nika
├── build.py                      # Empaquetado con PyInstaller
├── requirements.txt
├── assets/                       # Iconos e identidad visual
├── config/                       # Configuración local y perfiles
├── src/
│   ├── connection_manager.py     # Conexión USB/Bluetooth
│   ├── trigger_engine.py         # Efectos de gatillos adaptativos
│   ├── macro_engine.py           # Grabación y ejecución de macros
│   ├── profile_manager.py        # Perfiles, respaldos y paquetes .Nika
│   ├── appearance.py             # Preferencias visuales y presets sin Qt
│   ├── edit_history.py           # Historial de edición de Nexus
│   ├── single_instance.py        # Evita dos procesos peleando por el control
│   ├── crash_reporting.py        # Reportes locales de fallos inesperados
│   ├── input_studio.py           # Curvas, deadzones y drift
│   ├── gyro_engine.py            # Gyro Aim, calibración y Flick Stick
│   ├── advanced_mapping.py       # Mapper, gestos y capas por perfil
│   ├── diagnostics.py            # Métricas, capturas y reportes seguros
│   ├── game_profile_watcher.py   # Reglas automáticas y restauración
│   ├── virtual_feedback.py       # Rumble virtual hacia el DualSense físico
│   ├── hidhide_manager.py        # Doble entrada e integración oficial
│   ├── player_led_battery.py     # Batería en luces blancas del jugador
│   └── system_tray.py            # Bandeja del sistema
├── gui/
│   ├── modern_app.py             # Fachada pública compatible
│   ├── main_window.py            # Ventana, navegación y coordinación
│   ├── components.py             # Widgets visuales reutilizables
│   ├── ui_common.py              # Dependencias Qt compartidas
│   ├── pages/                    # Pantallas separadas por dominio
│   ├── design_system.py          # Tema, tarjetas, botones y avisos
│   └── app.py                    # Compatibilidad con imports anteriores
├── legacy/
│   └── customtkinter_app.py      # Interfaz anterior, fuera del arranque
├── docs/
│   ├── history/                  # Releases, hotfixes, reportes y validaciones
│   ├── ONBOARDING.md             # Funcionamiento del recorrido inicial
│   └── ...                       # Guías por módulo
├── installer/Nikaido.iss         # Instalador opcional con Inno Setup
└── tests/                        # Pruebas de compatibilidad y estabilidad
```

## Solución de problemas

### El control no se detecta

1. Asegurate de que el DualSense este emparejado en Bluetooth o conectado por USB
2. Prueba reiniciar el Bluetooth: `python main.py --reset-bt`
3. Verifica que los drivers del DualSense esten instalados

### Error al importar pydualsense

```cmd
pip install pydualsense hidapi
```

### La app no inicia

* Verifica que tengas Python 3.10+
* Ejecuta con `--debug` para ver logs detallados:

```cmd
  python main.py --debug
  ```

* Revisa los logs en: `%APPDATA%\\DualSenseController\\logs\\`

### Bluetooth no funciona correctamente

* La app incluye una herramienta de reinicio de Bluetooth que requiere permisos de administrador
* También puedes reiniciar manualmente desde la pestaña Configuración

## Dependencias

* **pydualsense**: Comunicacion con el DualSense
* **PySide6**: Interfaz gráfica Qt moderna
* **pillow**: Manipulacion de imagenes
* **pystray**: Icono en bandeja del sistema
* **pywin32**: Integracion con Windows
* **pyinstaller**: Empaquetado a .exe

## Licencia

Nikaido DualSense es software propietario. © Team Nikaido

No se permite redistribuir, vender, publicar, modificar ni extraer recursos del programa sin autorización escrita. Las ediciones Demo y Completa se rigen por el EULA incluido en `EULA_NIKAIDO.txt`. Los componentes de terceros conservan sus licencias originales; consulte `THIRD_PARTY_NOTICES.txt`.

Sony, PlayStation y DualSense son marcas registradas de Sony Interactive Entertainment. Nikaido no está afiliado con Sony.

---

## Nikaido Input Studio

La configuración de palancas por perfil se documenta en [`docs/INPUT_STUDIO.md`](docs/INPUT_STUDIO.md).

## Gestión de perfiles

En **Perfiles** puedes crear un preset basado en cualquier arma, darle nombre, descripcion, categoria e icono, o duplicar una tarjeta existente. Los perfiles personales se guardan automáticamente y también pueden eliminarse desde su tarjeta. Los perfiles incluidos se conservan como bases seguras para duplicar, y nunca se eliminan por accidente.

## Macros avanzadas

La guía para activadores, perfiles, palancas, gatillos y tiempos por acción está en [`docs/MACROS.md`](docs/MACROS.md).

## Remapeo avanzado

La guía de capas, gestos, atajos, acciones de teclado/ratón, macros y perfiles temporales está en [`docs/ADVANCED_MAPPING.md`](docs/ADVANCED_MAPPING.md).

## Créditos y referencias

- [MinHook](https://github.com/TsudaKageyu/minhook) por Tsuda Kageyu
- [HIDAPI](https://github.com/libusb/hidapi) por libusb/hidapi contributors
- [ViGEmBus](https://github.com/ViGEm/ViGEmBus) por Nefarius
- [DSX](https://dsx.ds4windows.com/) por Paliverse / DSX Team (inspiracion de funcionalidad)
- Protocolo DualSense reverse-engineering por la comunidad de PS4/PS5 homebrew



## Interfaz Qt

`gui/modern_app.py` es la interfaz activa. Está separada del motor HID para que el diseño pueda evolucionar sin duplicar los hilos que leen y escriben el control. Las pantallas reciben datos del backend existente y guardan sus cambios con `ProfileManager`.

Los cambios del touchpad y los gatillos multizona están documentados en [`docs/history/changes/CAMBIOS_TOUCHPAD_GATILLOS.md`](docs/history/changes/CAMBIOS_TOUCHPAD_GATILLOS.md). La vibración real de gatillos y su editor por perfil se detallan en [`docs/history/changes/CAMBIOS_VIBRACION_GATILLOS.md`](docs/history/changes/CAMBIOS_VIBRACION_GATILLOS.md).


## Código legado

La interfaz CustomTkinter anterior se conserva en `legacy/customtkinter_app.py` solo como referencia. No se carga ni se empaqueta en Nikaido 2.0.


## Nikaido KeyBridge

Convierte teclado y mouse en un control virtual Xbox 360 o DualShock 4 desde la sección Emulación. Incluye asignaciones editables, mouse como stick derecho, presets, rampas, suavizado y pausa rápida.
