# Reporte de auditoría profunda — Nikaido DualSense 2.9.4

## Alcance

Se revisaron arquitectura, persistencia, conexión HID, Bluetooth, emulación, gyro, macros, paquetes `.Nika`, luces, gatillos, perfiles automáticos, teclado/mouse, vibración virtual, bandeja y apagado. La meta fue encontrar fallos intermitentes, carreras entre hilos, datos corruptos y regresiones que las pruebas anteriores no cubrían.

## Errores corregidos

### Conexión y DualSense

1. **Reporte HID falso al iniciar.** La biblioteca puede exponer el atributo del reporte antes de haber recibido datos válidos. Nikaido acepta temporalmente el estado compatible durante una ventana de arranque y después exige actividad HID real si la biblioteca anunció esa fuente.
2. **Conexión fantasma antes del primer paquete.** Si `states` existía pero nunca producía datos, el fallback podía renovar la conexión para siempre. Ahora vence después de la gracia de inicio y entra el watchdog normal.
3. **Cierre doble del dispositivo.** Lectura, desconexión y cierre usan una ruta serializada; dos hilos no pueden cerrar el mismo objeto HID.
4. **Monitores duplicados.** Varias llamadas a `start()` ya no crean dos pares de hilos de conexión/estado.
5. **Trabajador HID anterior todavía vivo.** Un reinicio no crea otro lector encima de un hilo nativo que tarde en cerrar.
6. **Apagado lento.** Los monitores despiertan mediante eventos y no esperan a que termine el intervalo de sondeo.
7. **Reparación Bluetooth duplicada.** Solo una reparación puede ejecutarse a la vez.

### Giroscopio y passthrough DS4

1. La calibración y el bias dinámico aceptan únicamente secuencias HID nuevas.
2. Las animaciones de gatillos usan reloj monotónico y limitan saltos tras suspender/reanudar Windows.
3. El trabajador de animación no puede duplicarse al cambiar ajustes rápidamente.

### Macros y emulación

1. Se añadió propiedad por macro para botones, palancas y gatillos virtuales.
2. Cuando dos macros sostienen la misma entrada, terminar una ya no libera la entrada de la otra.
3. En entradas analógicas gana la macro activa más reciente; al terminar, reaparece el valor anterior.
4. Cambiar de perfil o recargar la biblioteca cancela ejecuciones antiguas.
5. El cierre general detiene explícitamente el motor de macros.
6. La grabación usa reloj monotónico para que un ajuste de hora de Windows no cree pausas negativas o gigantes.
7. Un paso desconocido se ignora de forma aislada y los pasos válidos permanecen.
8. Los avisos de pasos dañados se agrupan por macro para no llenar el registro con cientos de mensajes repetidos.
9. Valores directos `NaN`, infinitos o inválidos en palancas/gatillos se convierten a una posición neutral segura.

### Perfiles y `.Nika`

1. Los contenedores conocidos de `profiles.json` se reparan si llegan como texto, lista, número o `null`.
2. Las extensiones desconocidas se conservan para no romper compatibilidad futura.
3. Al importar, perfiles, macros, luces, gatillos, gyro e Input Studio se normalizan antes de tocar la configuración.
4. Un `input_studio` con tipo incorrecto ya no rompe la importación.
5. Las referencias internas de macros y del propio perfil se reasignan de manera transaccional.
6. El mapa avanzado válido se conserva sin reescrituras invisibles.
7. Los archivos temporales de exportación se limpian con una referencia segura incluso cuando la operación falla temprano.

### Ciclo de vida y concurrencia

Se protegieron contra arranque, parada o reinicio simultáneo:

- ConnectionManager
- VirtualFeedbackBridge
- GameProfileWatcher
- KeyboardGamepadEngine
- LightEffectEngine
- TriggerEngine
- MouseGyroSource
- TrayManager

Cada trabajador usa referencias o eventos de su propia generación cuando es necesario. Un hilo anterior no puede continuar porque un reinicio limpió un evento compartido, ni ser reemplazado mientras sigue atrapado en una llamada del sistema.

### Mouse, Raw Input y bandeja

1. El listener global de `Ctrl+M` conserva su referencia hasta terminar de verdad.
2. Una generación vieja de captura no puede reactivarse por el evento de una generación nueva.
3. Si Windows tarda en soltar un hook, se rechaza el reinicio en vez de crear una captura doble.
4. La ventana oculta de Raw Input ejecuta `DestroyWindow` una sola vez; antes podía hacerlo dos veces durante `WM_CLOSE`.
5. La bandeja evita iconos y trabajadores duplicados durante cierres lentos.

### Datos corruptos y estabilidad

1. Se añadió manejo de `OverflowError` a conversiones numéricas provenientes de configuración.
2. Valores como `1e309`, `Infinity`, `NaN` o cantidades enormes recuperan un valor seguro.
3. Se ejecutaron 25,000 estructuras aleatorias sobre nueve normalizadores sin excepciones.
4. Se corrigieron etiquetas de pasos de macro incompletos para evitar mostrar `None` al usuario.

## Pruebas agregadas

- Primer reporte crudo ausente, ventana de gracia y activación posterior del watchdog.
- Compatibilidad con controladores antiguos sin atributo de captura cruda.
- Desconexión concurrente con un solo cierre.
- Calibración y bias con secuencia repetida.
- Reparación Bluetooth concurrente.
- Propiedad concurrente de botones y valores analógicos de macros.
- Valores analógicos inválidos, infinitos y `NaN`.
- Cancelación por cambio de perfil y reloj del sistema alterado.
- Importación `.Nika` dañada y normalización de luces/perfil.
- Arranque simultáneo de conexión, gatillos, feedback, KeyBridge, luces, mouse y bandeja.
- Reinicio del callback de vibración virtual.
- Paso de macro corrupto entre pasos válidos.
- Apariencia con valores infinitos.

## Resultado automático

- **360 pruebas:** aprobadas.
- **Ruff:** limpio.
- **Compileall:** limpio.
- **Diff check:** limpio.
- **Fuzz de configuración:** 25,000 casos × 9 normalizadores, sin caídas.
- **Auto‑prueba DS4 extendido:** aprobada.
- **Auto‑prueba general de perfiles, rumble y mouse:** aprobada.
- **Temas de interfaz:** 10/10 pruebas aprobadas.
- **Touchpad multizona:** aprobado.
- **Bandit:** 0 graves, 0 medios y 43 avisos bajos revisados. Los avisos bajos corresponden principalmente a procesos del sistema lanzados con listas de argumentos y bloques de recuperación intencionales.

## Lista manual recomendada en Windows

1. Conectar por USB, desconectar durante movimiento y reconectar.
2. Repetir por Bluetooth, observar el arranque durante al menos 10 segundos y dejar dormir el control hasta que Nikaido detecte la desconexión.
3. Probar gyro passthrough DS4 en reposo, pitch, yaw y roll por separado.
4. Calibrar gyro sin mover el control y después intentar calibrar mientras se mueve.
5. Lanzar dos macros que sostengan el mismo botón y dos valores distintos de palanca.
6. Cambiar de perfil mientras corre una macro larga.
7. Activar/desactivar emulación y confirmar que el rumble vuelve después del reinicio.
8. Alternar Ctrl+M, cambiar perfiles y reiniciar captura de mouse varias veces.
9. Minimizar/restaurar desde bandeja repetidamente y cerrar desde el menú.
10. Exportar/importar `.Nika` con imagen, macros, luces, Nexus e Input Studio.
11. Cerrar Nikaido durante actividad y confirmar que no queda ningún proceso, botón, cursor o vibración retenida.

## Limitación honesta

No se generó ni validó un `.exe` de Windows en este entorno. Tampoco se pudo probar físicamente DualSense, ViGEm, HidHide, Raw Input o Bluetooth. PySide6 no estaba instalado, por lo que la ventana gráfica completa no pudo abrirse; sí se ejecutaron las pruebas de lógica y temas que no requieren esa dependencia. La entrega es código fuente auditado y preparado para compilar y validar en Windows.
