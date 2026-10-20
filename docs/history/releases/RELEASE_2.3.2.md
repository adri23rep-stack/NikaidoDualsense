# Nikaido DualSense 2.3.2

## Bandeja inteligente con batería

La bandeja del sistema dejó de ser un icono estático. Ahora representa el estado real del DualSense sin abrir la ventana principal.

### Icono dinámico

- Mantiene el logo de Nikaido como base.
- Incluye un medidor de batería visible incluso cuando Windows reduce el icono.
- Verde: batería saludable.
- Amarillo: batería media.
- Rojo: batería baja.
- Cian con rayo: el control está cargando.
- Gris con marca roja: DualSense desconectado.
- Estado neutro mientras llega el primer informe de batería después de conectar.

### Interacción

- Clic izquierdo o doble clic: restaura Nikaido.
- Clic derecho: abre el menú rápido.
- El menú muestra conexión, batería exacta y perfil activo.
- Permite cambiar de perfil sin abrir la ventana.
- **Salir de Nikaido** cierra motores, bandeja y proceso completo.

### Al minimizar

- Si `Enviar a la bandeja al minimizar` está activo, la ventana desaparece de la barra de tareas y Nikaido permanece junto al reloj.
- La primera vez de cada sesión aparece una notificación indicando cómo recuperar la ventana.
- Si la bandeja no está disponible, Nikaido se minimiza normalmente y nunca queda invisible.

## Estabilidad

- Render de iconos con caché para evitar trabajo repetido.
- Límite de caché para impedir crecimiento indefinido.
- Actualización protegida por bloqueo entre el hilo HID y el hilo de bandeja.
- Menú y tooltip se reconstruyen cuando cambia batería, conexión o perfil.
- Callbacks duplicados se ignoran.
- El build de Windows ahora prueba HID, pydualsense, pystray, Pillow y el render del icono antes de generar el ZIP final.

## Compatibilidad

- No cambia el formato `.Nika`.
- No cambia `CONFIG_VERSION`.
- No modifica HID, ViGEm, gyro, macros ni perfiles.
