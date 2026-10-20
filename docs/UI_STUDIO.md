# Nikaido UI Studio

Nikaido UI Studio permite reemplazar la pantalla principal de Nikaido DualSense con una interfaz diseñada visualmente. La lógica del control permanece en la aplicación clásica; el tema solo decide qué se muestra y qué acción registrada se ejecuta al pulsar un elemento.

## Inicio rápido

1. Abre **Configuración > Interfaz personalizada > Abrir UI Studio**.
2. En el editor usa **Archivo > Crear plantilla inicial**.
3. Mueve, redimensiona y edita los elementos.
4. Pulsa **Aplicar ahora** para probar el diseño sin cerrar el editor.
5. Guarda como `*.nikaido-ui.json` o exporta un paquete `*.nikaido-theme`.
6. Activa **Cargar interfaz personalizada al iniciar** cuando el diseño ya esté guardado.

`F12` alterna entre la interfaz personalizada y la clásica. Esta salida siempre permanece disponible aunque el tema esconda sus propios botones de navegación.

## Elementos

| Elemento | Uso |
|---|---|
| Imagen/GIF | Fondos, iconos, botones dibujados y animaciones. |
| Texto | Etiquetas y datos dinámicos. |
| Globo de texto | Mensajes con cola izquierda, central o derecha. |
| Botón | Botón real con texto y estados normal, hover y presionado. |
| Barra dinámica | Indicador enlazado a batería, L2, R2 u otra variable numérica. |
| Rectángulo/Elipse | Tarjetas, fondos y figuras clicables. |
| Zona invisible | Hace clicable una región de una ilustración sin dibujar encima. |

Todos los elementos admiten posición, tamaño, rotación, opacidad, orden de capa, visibilidad, bloqueo, tooltip y acción. Las imágenes también pueden tener archivos distintos para los estados hover y presionado.

## Pantallas

Un diseño puede contener varias pantallas internas, por ejemplo `main`, `profiles` y `tools`.

- `page.open` abre otra pantalla del tema.
- `page.back` regresa a la pantalla anterior.
- Un elemento asignado a la pantalla `*` aparece en todas, útil para fondos, batería y navegación.
- La pantalla marcada como **Inicial** se abre al cargar el tema.

## Acciones disponibles

Las acciones son identificadores seguros. Un tema no puede ejecutar Python, comandos ni archivos externos.

### Navegación y aplicación

- `page.open`, `page.back`
- `navigate.profiles`, `navigate.buttons`, `navigate.triggers`
- `navigate.macros`, `navigate.input_studio`, `navigate.settings`
- `ui.editor`, `ui.reload`, `ui.standard`, `ui.custom`, `ui.disable`
- `window.fullscreen.toggle`, `app.minimize`, `app.close`

### Control y perfiles

- `controller.connect`, `controller.disconnect`
- `profile.next`, `profile.previous`, `profile.import`, `profile.export`
- `profile.apply` con argumentos: `{"profile_id": "sniper"}`
- `trigger.reset`, `buttons.reset`

### Emulación y utilidades

- `emulation.xbox`, `emulation.ps4`, `emulation.off`
- `macro.new`, `macro.toggle`
- `macro.play` con argumentos: `{"macro_id": "mi_macro"}`
- `led.choose`, `bluetooth.reset`
- `player.set` con argumentos: `{"player": 1}`

## Variables dinámicas

Las variables se escriben entre llaves dentro de textos, botones, globos, tooltips y etiquetas de barras.

| Variable | Ejemplo |
|---|---|
| `{connection}` | Conectado / Desconectado |
| `{connection_type}` | USB / BLUETOOTH |
| `{battery}` | 87 |
| `{battery_percent}` | 87% |
| `{charging}` | Sí / No |
| `{active_profile}` | Rifle de asalto |
| `{active_profile_id}` | assault_rifle |
| `{profile_count}` | 8 |
| `{emulation_mode}` | Xbox 360 |
| `{macros_enabled}` | Sí / No |
| `{status}` | Último mensaje de la aplicación |
| `{l2}`, `{r2}` | Valor actual del gatillo |
| `{time}`, `{date}` | Hora y fecha locales |
| `{current_page}` | Pantalla interna activa |

Una barra dinámica usa el nombre sin llaves en **Variable barra**, por ejemplo `battery`, `l2` o `r2`.

## Visibilidad condicional

- `always`
- `controller.connected`
- `controller.disconnected`
- `battery.charging`
- `battery.low`
- `connection:usb`
- `connection:bluetooth`
- `profile:ID`
- `not:condición`

Ejemplo: dos botones pueden ocupar el mismo lugar. Uno usa `controller.disconnected` para conectar y el otro `controller.connected` para desconectar.

## Archivos y portabilidad

### JSON local

`*.nikaido-ui.json` es editable y cómodo durante el desarrollo. Al guardarlo, UI Studio copia las imágenes a una carpeta vecina para evitar rutas absolutas rotas. En el ejecutable, el espacio de trabajo se guarda dentro del directorio de configuración del usuario, no en la carpeta temporal de PyInstaller.

### Paquete portable

`*.nikaido-theme` es un ZIP controlado que contiene:

```text
manifest.json
assets/
  fondo_....png
  boton_....gif
```

Los recursos se deduplican por contenido. La importación bloquea rutas inseguras y limita el tamaño descomprimido del paquete.

## Recuperación y pruebas

- El editor conserva hasta 60 estados para deshacer y rehacer.
- Hay autoguardado de recuperación cada 30 segundos.
- El guardado usa reemplazo atómico para reducir archivos truncados.
- **Validar diseño** revisa pantallas, colores, acciones, condiciones, argumentos y recursos.
- **Aplicar ahora** crea una vista real dentro de Nikaido, no una captura simulada.

## Arquitectura

```text
gui/ui_theme.py            Modelo, migración, validación y paquetes
gui/interface_editor.py    Editor visual
gui/interface_renderer.py  Renderer de ejecución
gui/app.py                 Registro de acciones y conexión con Nikaido
```

El renderer está separado de la interfaz clásica. Aplicar un tema no destruye los widgets originales, por eso `F12` puede restaurarlos inmediatamente.
