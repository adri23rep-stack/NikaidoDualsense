# Reporte técnico — Nikaido DualSense 2.5.5

## Objetivo

Hacer que Ctrl + M funcione como un interruptor inmediato durante la partida y garantizar que el aviso flotante no bloquee clics sobre el juego.

## Implementación

### Reactivación inmediata

Se separaron dos rutas de inicio:

- **Inicio manual:** conserva `start_delayed(5.0)` para dar tiempo de abrir o enfocar el juego.
- **Reactivación con Ctrl + M:** usa `start()` directamente y vuelve a registrar la captura sin temporizador.

KeyBridge y Mouse → Gyro tienen helpers propios para esta ruta inmediata. Ambos mantienen armada la escucha global de Ctrl + M y restauran el estado de pausa si Windows no permite iniciar la captura.

### Estado y mensajes

La acción de reactivación se registra como `enabled`, por lo que la interfaz muestra la confirmación correcta y el overlay cambia directamente de **MOUSE LIBERADO** a **MOUSE ACTIVADO**, sin pasar por 5, 4, 3, 2, 1.

### Click-through reforzado

La transparencia a entrada ya no depende de un solo atributo Qt. Se combinan:

1. bandera Qt `WindowTransparentForInput`;
2. `WA_TransparentForMouseEvents` en contenedor e hijos;
3. ventana sin foco;
4. estilos extendidos nativos de Windows;
5. `HTTRANSPARENT` durante `WM_NCHITTEST`.

Esta combinación evita que el rectángulo o cualquiera de sus textos consuma clics dirigidos al juego.

## Compatibilidad preservada

La primera activación sigue usando cinco segundos. No se modificó la respuesta del stick, la sensibilidad, el suavizado, el recentrado, el cursor original, Raw Input, el hook global ni el sondeo de respaldo.

## Validación realizada

- **232 pruebas aprobadas.**
- `compileall` de todo el proyecto aprobado.
- Versión consistente en código, paquete e instalador: **2.5.5**.
- Pruebas de reactivación inmediata para las dos funciones.
- Prueba que confirma que la activación inicial mantiene el retraso.
- Verificación estructural del click-through Qt/Windows.

## Límite del entorno

El entorno de construcción no tiene PySide6, backend HID ni escritorio Windows. Por eso no fue posible ejecutar la auto-prueba HID ni comprobar físicamente el hit-test encima de Zelda; esa última validación corresponde a Windows con el juego abierto.
