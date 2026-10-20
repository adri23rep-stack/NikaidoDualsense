# Hotfix 2.5.5 — Reactivación instantánea y overlay click-through

Este hotfix pule el flujo de Mouse → Stick y Mouse → Gyro después de probarlo dentro de juegos reales.

## Cambios

- La cuenta visible de **5 segundos** se conserva únicamente cuando la opción se activa desde la interfaz de Nikaido.
- Después de liberar el cursor con **Ctrl + M**, una segunda pulsación reactiva el mouse **al instante**.
- La reactivación ya no entra al estado de cuenta regresiva ni espera otros cinco segundos.
- Mouse → Stick y Mouse → Gyro comparten el mismo comportamiento.
- Si la captura inmediata falla, el estado queda liberado y el diagnóstico conserva el error real.

## Aviso atravesable

`MouseCaptureOverlay` ahora aplica varias capas de protección para no interceptar el juego:

- `WindowTransparentForInput` cuando está disponible en Qt;
- `WA_TransparentForMouseEvents` en la ventana y en cada etiqueta hija;
- política de foco `NoFocus`;
- estilos nativos `WS_EX_TRANSPARENT`, `WS_EX_LAYERED` y `WS_EX_NOACTIVATE` en Windows;
- respuesta `HTTRANSPARENT` al hit-test nativo de Windows.

El mensaje puede permanecer encima del juego, pero los clics deben llegar a la ventana que está debajo.

## Compatibilidad

No se modificaron sensibilidad, suavizado, recentrado, Raw Input, respaldos de captura, gyro físico, Nexus, perfiles, macros ni vibración.

## Validación

- 232 pruebas automatizadas aprobadas.
- Compilación de todos los módulos Python aprobada.
- Pruebas específicas para reactivación instantánea en KeyBridge y Mouse → Gyro.
- Prueba de conservación del retraso inicial de cinco segundos.
- Verificación estructural de las capas Qt y Windows de click-through.

La comprobación final del click-through nativo requiere Windows gráfico y un juego real.
