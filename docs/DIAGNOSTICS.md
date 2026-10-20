# Centro de diagnóstico

La sección **Diagnóstico** muestra lo que ocurre entre el DualSense físico, la ruta rápida de Nikaido y el control virtual. Está diseñada para investigar errores sin añadir trabajo pesado al hilo de entrada.

## Qué mide

- **HID físico:** frecuencia estimada del DualSense usando el avance real del contador Sony. Puede rondar 250 Hz aunque Nikaido no procese cada informe individual.
- **Procesamiento:** ticks por segundo que Nikaido completa en la ruta de entrada.
- **Estados nuevos:** copias distintas que Nikaido alcanzó a observar. No equivale a la frecuencia física y no se usa como indicador de pérdida.
- **Control virtual:** actualizaciones por segundo enviadas a ViGEm.
- **Ruta promedio y p95:** tiempo interno desde comenzar la lectura hasta terminar la salida virtual.
- **Botón p95:** tiempo de la ruta medido únicamente cuando ocurre una pulsación o liberación.
- **ViGEm promedio:** duración de la escritura del control virtual.
- **Lecturas fallidas:** fallos consecutivos reales al consultar el DualSense.
- **Informes intermedios:** estados que fueron reemplazados por uno más nuevo antes del siguiente tick. Son normales cuando el dispositivo produce datos más rápido que el observador y **no significan paquetes perdidos**.
- **Reinicios de secuencia:** saltos grandes o reinicios del contador HID, por ejemplo al reconectar.
- **Gyro procesado:** frecuencia de secuencias nuevas que Gyro Engine observa. No se calcula con callbacks agrupados.
- **Proceso:** RAM, CPU e hilos de Nikaido.

## Cómo interpretar las frecuencias

Un reporte puede mostrar, por ejemplo:

- HID físico: 250 Hz;
- procesamiento de Nikaido: 125 Hz;
- estados nuevos observados: 65–70 Hz;
- control virtual: 125 Hz.

Eso no implica pérdida del USB. El hilo de Nikaido consulta una copia compartida del último reporte; si el DualSense generó varios informes entre dos consultas, se conserva el más reciente y los demás se cuentan como **intermedios omitidos**.

## Capturar un problema

1. Abre **Diagnóstico**.
2. Elige 10, 20 o 30 segundos.
3. Presiona **Iniciar captura**.
4. Reproduce el error dentro del juego o probador.
5. Detén la captura o espera a que termine.
6. Presiona **Generar reporte**.

El ZIP incluye `report.json`, `capture.json`, `summary.txt` y una nota de privacidad.

Cada muestra de `capture.json` contiene:

- `physical`: botones, sticks, gatillos, gyro y acelerómetro físicos;
- `virtual`: estado efectivo enviado a ViGEm;
- `timing`: ruta total, trabajo en tiempo real, ViGEm y tiempo desde la copia física hasta la salida virtual;
- campos planos compatibles con lectores de reportes 2.1.0.

## Privacidad

El reporte no incluye:

- nombre de usuario de Windows;
- rutas personales;
- argumentos de procesos;
- contenido de macros;
- archivos o imágenes de perfiles.

Sí incluye información técnica como versión de Windows, arquitectura, frecuencia de entrada y nombres conocidos de programas que pueden producir doble entrada.

## Programas en conflicto

La presencia de DS4Windows, DualSenseX, reWASD u otra capa de emulación se marca como posible conflicto. Steam aparece como aviso informativo porque solo causa doble entrada cuando Steam Input está activo para ese juego.
