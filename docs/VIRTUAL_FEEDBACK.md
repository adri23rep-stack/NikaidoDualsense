# Vibración del juego hacia el DualSense

Nikaido 2.5 registra las notificaciones de feedback del control virtual creado por ViGEm y las devuelve a los motores físicos del DualSense.

## Flujo seguro

1. El juego envía vibración al Xbox 360 o DualShock 4 virtual.
2. `EmulatorManager` recibe la notificación y publica únicamente el último valor.
3. `VirtualFeedbackBridge` procesa ese valor en un hilo independiente.
4. Se aplican fuerza, balance, intercambio de motores, suavizado y un apagado de seguridad.
5. Al cambiar de emulación, desconectar o cerrar Nikaido, ambos motores se neutralizan.

El callback de ViGEm nunca escribe directamente al HID. Esto evita meter trabajo de controladores dentro del callback y reduce el riesgo de bloqueos o vibración pegada.

## Ajustes

La sección **Vibración → Vibración del juego** permite:

- activar o apagar el puente;
- ajustar fuerza global;
- ajustar los motores izquierdo y derecho por separado;
- intercambiar motores;
- suavizar cambios bruscos;
- elegir el tiempo de apagado si el juego deja de mandar datos.

El estado en vivo indica si la emulación está activa, si ViGEm aceptó el callback y cuántos eventos se han recibido.
