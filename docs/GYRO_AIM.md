# Gyro Studio y Flick Stick

Nikaido procesa el giroscopio dentro del mismo ciclo que actualiza el control virtual. Botones, sticks, gatillos y sensores provienen del mismo paquete HID completo, evitando mezclar datos de instantes distintos.

## Modos

- **Passthrough DS4:** copia giroscopio, acelerómetro, timestamp, batería y touchpad al reporte extendido del DualShock 4 virtual.
- **Mouse:** convierte yaw y pitch en movimiento relativo del mouse.
- **Stick derecho:** convierte yaw y pitch en salida del stick virtual.
- **Desactivado:** libera cualquier salida del motor.

Los ajustes se guardan por perfil. Los perfiles antiguos cargan con las funciones nuevas apagadas.

## Activación

Gyro Aim puede funcionar:

- siempre;
- mientras se mantiene L2;
- mientras se mantiene cualquier botón elegido;
- al tocar el touchpad;
- con una pulsación que alterna activo/apagado;
- en modo invertido, activo mientras el botón no está presionado.

El umbral de gatillo evita activar L2 por ruido analógico.

## Respuesta

Los controles principales son:

- sensibilidad horizontal y vertical;
- inversión por eje;
- zona muerta del sensor;
- suavizado;
- salida mínima;
- velocidad máxima del mouse;
- aceleración opcional;
- filtro de drift;
- frecuencia de referencia para el primer cálculo al conectar.

Para salida como stick también hay sensibilidad, zona muerta, anti-zona muerta, salida máxima, curva y mezcla con la palanca física.

Durante el juego, el motor sigue la frecuencia HID real del DualSense. La frecuencia de referencia no limita ni ralentiza la entrada; solo estabiliza el primer intervalo después de conectar o cambiar de perfil.

### Modos de mezcla

- **Sumar:** combina palanca física y gyro.
- **Reemplazar:** utiliza solo gyro mientras está activo.
- **Priorizar gyro:** da prioridad al movimiento del gyro y deja pasar la palanca cuando el sensor está en reposo.

## Presets

- **Suave:** mayor filtro y respuesta tranquila.
- **Equilibrado:** punto de partida general.
- **Competitivo:** poco suavizado y zona muerta baja.
- **Gyro como stick:** configuración base para juegos que solo aceptan cámara analógica.

Los presets cambian únicamente valores relacionados con la sensación y pueden ajustarse después.

## Flick Stick

Flick Stick usa la palanca derecha para elegir una dirección de giro y deja el giroscopio para la precisión fina.

- arriba equivale a `0°`;
- derecha a `+90°`;
- izquierda a `-90°`;
- abajo a `180°`.

Al superar el umbral, Nikaido genera el giro inicial. Si después recorres el borde del stick, envía las diferencias angulares de forma continua.

### Salida Mouse

`Píxeles por grado` calibra cuánto debe mover el mouse para cada grado. Una vuelta de 180° genera aproximadamente:

```text
180 × píxeles_por_grado
```

`Duración del giro` reparte el movimiento para evitar un salto demasiado brusco.

### Salida Stick derecho

Como un stick no puede pedir un ángulo exacto, `Tiempo para 180°` indica cuánto tarda el juego en girar media vuelta con el stick al máximo. Nikaido mantiene la salida el tiempo proporcional al ángulo pendiente.

Mientras Flick Stick está activo, la palanca física se neutraliza para que el juego no reciba simultáneamente el stick normal y el giro generado.

## Calibración

1. Coloca el control en una superficie estable.
2. Presiona **Calibrar**.
3. No lo muevas hasta que termine.

La calibración usa la mediana de cada eje y valida que giroscopio y acelerómetro estén estables. Si detecta movimiento, rechaza el resultado en lugar de guardar un centro falso.

## Passthrough DS4

El passthrough usa el orden real del reporte DualSense: primero gyro X/Y/Z y después acelerómetro X/Y/Z. Construye un reporte DS4 extendido de 63 bytes y no comparte la salida de Gyro Aim o Flick Stick.

## Mouse → Gyro

Esta fuente opcional convierte el movimiento del mouse en sensor virtual DS4. Está apagada por defecto y permite sensibilidad, inversión, límite de velocidad y mezcla con el movimiento físico.

## Diagnóstico rápido

Con hardware conectado:

```bat
python tools\gyro_live_diagnostic.py
```

Prueba de construcción sin hardware:

```bat
python tools\gyro_report_selftest.py
```
