# Reporte técnico — Nikaido DualSense 2.1.0

## Resumen

Nikaido DualSense 2.1.0 parte de la versión 2.0.4 y agrega las tres prioridades con mayor impacto sin cambiar el formato `.Nika`, sin borrar configuraciones anteriores y sin alterar la ruta estable del giroscopio passthrough DS4.

La prioridad del trabajo fue mantener la entrada rápida: el mapper avanzado se ejecuta dentro del mismo ciclo HID antes de ViGEm, mientras que el diagnóstico observa una copia secundaria limitada a 60 Hz.

## Lista oficial de prioridades

1. **Centro de diagnóstico profesional** — implementado en 2.1.0.
2. **Modos avanzados de botones y capas** — implementado en 2.1.0.
3. **Gyro Aim avanzado y Flick Stick** — implementado en 2.1.0.
4. Overlay discreto dentro de juegos.
5. Actualizador con restauración.
6. Compatibilidad con varios controles.
7. Biblioteca comunitaria de perfiles.
8. Importadores de otras herramientas.
9. Modo portátil.
10. API versionada de extensiones.

El archivo `docs/history/roadmaps/ROADMAP_2.1.md` incluido en el proyecto contiene el alcance y los criterios de calidad de cada prioridad.

## 1. Centro de diagnóstico

Se añadió `src/diagnostics.py` y una nueva pantalla **Diagnóstico**.

### Funciones

- Frecuencia de sondeo y frecuencia HID física real.
- Frecuencia y duración de la actualización del control virtual.
- Tiempo interno promedio, p95 y máximo desde lectura hasta salida virtual.
- Conteo de reportes nuevos, repetidos, perdidos, crudos y fallback.
- Vista en vivo de botones, sticks, gatillos, gyro y acelerómetro.
- RAM, CPU e hilos del proceso.
- Estado del mapper, capa activa y botones bloqueados.
- Estado del giroscopio, calibración y Flick Stick.
- Capturas de 10, 20 o 30 segundos.
- Detección asíncrona de posibles programas de doble entrada.
- Exportación de un ZIP técnico con `report.json`, `capture.json`, `summary.txt` y nota de privacidad.

### Privacidad y rendimiento

- No guarda contenido de macros, perfiles ni argumentos de procesos.
- Sanitiza nombres de usuario y rutas personales, incluso dentro de mensajes de error externos.
- La captura usa memoria limitada y nunca escribe en HID o ViGEm.
- El escaneo de procesos se ejecuta fuera del hilo de la interfaz.
- La vista secundaria está limitada a 60 Hz para no añadir retraso al control.

## 2. Mapper avanzado por perfil

Se amplió `src/advanced_mapping.py` y se añadió un editor visual dentro de **Mapper**.

### Gestos

- Mientras se mantiene.
- Al presionar.
- Al soltar.
- Pulsación corta.
- Pulsación larga.
- Doble pulsación.
- Alternar encendido/apagado.
- Reserva exclusiva de doble pulsación para que no se dispare también la acción simple.

### Acciones

- Botón virtual.
- Teclado y combinaciones.
- Botones o movimiento del mouse.
- Macros.
- Cambio de perfil.
- Cambio de capa.
- Recentrar, activar, desactivar o alternar giroscopio.
- Desactivar el botón físico.
- Passthrough del botón original.

### Capas y estabilidad

- Capa `base` heredable.
- Condiciones como `L1 + X`.
- Los cambios de capa se resuelven antes que los demás botones del mismo paquete HID.
- Capas temporales y alternables.
- Apilado seguro: los modificadores pueden soltarse en cualquier orden sin terminar en la capa incorrecta.
- Turbo configurable y bloqueo selectivo de la entrada original.
- Los botones sin reglas no recorren el editor avanzado, manteniendo baja la carga por paquete.
- Los cambios de perfil esperan a que termine el gesto físico para evitar teclas o botones pegados.

### Perfiles y `.Nika`

- Cada perfil guarda su propio `advanced_mapping_config`.
- Las exportaciones `.Nika` incluyen las capas y reglas dentro de `profile.json`.
- `NIKA_FORMAT_VERSION` continúa en 1 porque el campo nuevo es opcional y compatible.
- El mapa global de Nikaido 2.0 se conserva solamente como respaldo de migración.

## 3. Gyro Aim avanzado y Flick Stick

Se amplió `src/gyro_config.py`, `src/gyro_engine.py` y la pantalla **Gyro Studio**.

### Gyro Aim

- Salida como mouse, stick derecho o passthrough DS4.
- Activación siempre, con L2, con cualquier botón, touchpad, alternar o invertida.
- Sensibilidad horizontal y vertical separadas.
- Zona muerta, suavizado, aceleración, salida mínima y velocidad máxima.
- Curvas lineal, exponencial y de precisión.
- Mezcla con la palanca física: sumar, reemplazar o priorizar gyro.
- Presets Suave, Equilibrado, Competitivo y Gyro como stick.
- Ajustes, calibración y telemetría separados por perfil.

### Flick Stick

- La palanca derecha selecciona el ángulo de giro.
- Arriba = 0°, derecha = +90°, izquierda = -90° y abajo = 180°.
- Umbral de entrada y umbral de liberación separados.
- Ángulo mínimo para evitar giros accidentales.
- Giro continuo al recorrer el borde de la palanca.
- Salida por mouse calibrable en píxeles por grado.
- Salida por stick calibrable mediante tiempo para 180°.
- Reparto temporal del giro para evitar saltos bruscos.
- Neutralización de la palanca física únicamente mientras Flick Stick la utiliza.
- Flick Stick permanece apagado por defecto en perfiles existentes.

La frecuencia HID real sigue controlando el procesamiento durante el juego. El valor mostrado como frecuencia de referencia solo estabiliza el primer cálculo después de conectar o cambiar de perfil.

## Compatibilidad

- `APP_VERSION`: `2.1.0`.
- `CONFIG_VERSION`: permanece en `2.0.0`.
- `NIKA_FORMAT_VERSION`: permanece en `1`.
- Perfiles antiguos, macros, Input Studio, RGB, calibración y giroscopio passthrough conservan su estructura.
- Las funciones nuevas llegan apagadas o con valores seguros en configuraciones anteriores.
- No se eliminó la ruta básica de remapeo; el mapper avanzado se suma encima y puede bloquear selectivamente la entrada física.

## Validación realizada

- **131 pruebas automatizadas aprobadas.**
- Compilación sintáctica completa con `compileall`.
- Importación correcta de todos los módulos que no dependen de PySide6 en este entorno.
- Pruebas de serialización y copia profunda del mapper por perfil.
- Prueba de exportación/importación `.Nika` con reglas avanzadas.
- Pruebas de doble pulsación exclusiva, liberación, turbo, combos, cambio de perfil y capas apiladas.
- Pruebas de Flick Stick, dirección, umbral y salida.
- Pruebas de captura, privacidad y creación del reporte diagnóstico.
- Microprueba interna del mapper: sin reglas ronda 1.8 microsegundos por ciclo y con una regla ronda 2.8 microsegundos por ciclo en este entorno. No representa la latencia física de Windows o ViGEm.

## Limitaciones de esta validación

Este entorno no dispone de Windows, PySide6, ViGEm ni un DualSense físico. Por eso no fue posible comprobar aquí:

- apariencia final con escalado real de Windows;
- inyección real de teclado y mouse mediante `pywin32`;
- latencia física USB/Bluetooth;
- salida real ViGEm;
- calibración de Flick Stick dentro de juegos concretos.

La primera prueba recomendada en Windows es abrir **Diagnóstico**, iniciar una captura de 10 segundos y probar cada gesto, capa y modo de gyro con un perfil de prueba antes de usarlo en una partida.
