# Nikaido DualSense 2.0.1 — Hotfix de entrada y UI

Este parche se limita a los problemas reportados después de la versión 2.0.0. No cambia el formato `.Nika`, la estructura de perfiles ni las configuraciones existentes.

## Giroscopio DS4 passthrough

- El reporte DS4 extendido ahora resta el centro guardado por la calibración de giroscopio del perfil.
- Al activar passthrough realiza un centrado corto de reposo para eliminar el sesgo natural del sensor cuando no existe una calibración previa.
- La corrección adaptativa queda limitada a movimientos pequeños y estables para no cancelar giros reales.
- Una calibración nueva se aplica al DS4 virtual inmediatamente.

## Latencia de palancas emuladas

- Gyro, macros y remapeo se procesan antes de enviar el reporte a ViGEm.
- La interfaz, monitor, touchpad y efectos físicos se notifican después, fuera de la ruta crítica.
- El bucle mantiene un periodo total de 120 Hz; ya no suma una espera fija al tiempo de procesamiento.
- Input Studio reutiliza la configuración ya validada en lugar de reconstruirla dos veces por lectura.
- Se crea una sola copia del estado del control por reporte.

## Pestañas

- Nuevo estilo consistente con el diseño oscuro de Nikaido.
- Títulos sin recorte.
- Desplazamiento horizontal cuando no caben todas las pestañas.
- Botones de desplazamiento integrados visualmente.

## Grabación de macros

- Las acciones aparecen en la tabla mientras se graban.
- Contador en vivo y desplazamiento automático a la acción más reciente.
- Se conserva la secuencia anterior cuando no se detecta ninguna entrada.
- Cancelar el editor detiene correctamente una grabación activa.

## Validación

- 96 pruebas automáticas aprobadas.
- Compilación sintáctica completa aprobada.
- Compatibilidad de perfiles, macros y formato `.Nika` conservada.
