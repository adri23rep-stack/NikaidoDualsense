# Reporte técnico — Nikaido DualSense 2.5.4

## Objetivo

Resolver el problema de uso provocado por la captura inmediata del cursor: al activar Mouse → Stick o Mouse → Gyro no había tiempo para abrir el juego, y Ctrl + M solo apagaba la función sin permitir reactivarla.

## Implementación

### Captura armada con retraso

`MouseGyroSource` incorpora un inicio diferido de 5 segundos. Durante ese periodo informa el tiempo restante sin iniciar Raw Input, el hook global, el sondeo de respaldo ni el recentrado. La cuenta puede cancelarse de forma segura.

### Atajo persistente

La escucha de Ctrl + M se separó del hilo de captura. Así permanece disponible durante la cuenta y mientras el mouse está liberado. El atajo alterna el estado de ejecución, pero no modifica la preferencia guardada del usuario.

### KeyBridge

- Mouse → Stick queda configurado aunque se pause temporalmente.
- Al liberar, se ponen en cero los ejes del stick derecho.
- Al reactivar, se lanza una nueva cuenta de 5 segundos.
- El teclado y el mando virtual siguen funcionando.

### Mouse → Gyro

- La pausa afecta únicamente los deltas de mouse enviados al sensor DS4 virtual.
- El gyro físico no se desactiva.
- Al volver desde la fuente KeyBridge a DualSense, la captura puede armarse de nuevo si estaba configurada.

### Aviso visible

Se añadió `MouseCaptureOverlay`, una ventana Qt independiente, siempre arriba, sin foco y transparente a clics. Presenta:

- cuenta 5–1;
- instrucción para abrir el juego;
- aviso grande de Ctrl + M;
- confirmación visual ON/OFF.

## Compatibilidad preservada

No se modificaron Nexus, macros, perfiles automáticos, feedback de vibración, HidHide, calibración, gatillos ni el procesamiento del gyro físico.

## Límites de validación

Las pruebas automatizadas confirman lógica, estados, cancelación, persistencia y estructura de interfaz. Este entorno no tiene Windows gráfico, PySide6 ni hardware DualSense, por lo que la posición real del overlay, el atajo global dentro de juegos con anticheat y el comportamiento multimonitor deben probarse físicamente.

## Resultado de validación

- **228 pruebas automatizadas aprobadas.**
- Compilación de todos los módulos Python aprobada.
- Auto-prueba de Nikaido 2.5 aprobada con versión 2.5.4.
- Cuenta repetida protegida para no reiniciar el temporizador por refrescos de configuración.
- El código conserva la configuración al alternar Ctrl + M.
