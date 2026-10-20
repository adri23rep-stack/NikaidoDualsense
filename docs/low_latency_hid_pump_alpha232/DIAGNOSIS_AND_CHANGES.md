# Diagnóstico y cambios — Alpha 2.3.2

## Causa atacada

La ruta anterior aceleró el sondeo de Nikaido, pero seguía dependiendo del hilo interno de pydualsense. Ese hilo realiza por cada paquete: lectura HID, decodificación completa y eventos, copia profunda del estado, preparación de salida y escritura física. Si una escritura USB/Bluetooth tarda, la siguiente lectura puede recoger paquetes ya encolados y la entrada virtual se siente atrasada.

## Cambio

- Nikaido reemplaza `sendReport` antes de iniciar pydualsense.
- Cada paquete recibido se normaliza USB/Bluetooth y se publica en `controller.states` mediante una sola asignación atómica.
- No se llama `readInput`, por lo que la ruta crítica evita eventos y `deepcopy`.
- Las salidas físicas corren en un hilo separado a 60 Hz y solo se escriben al cambiar o cada 250 ms; una escritura lenta ya no detiene las lecturas HID.
- Un `threading.Event` despierta el pipeline virtual al llegar un informe nuevo.
- Si la instalación de la bomba no es compatible, se conserva el comportamiento anterior.

## Límites

El entorno de revisión no posee DualSense, ViGEmBus ni Windows. La hipótesis está respaldada por la estructura del código y pruebas simuladas, pero la mejora final debe medirse físicamente en USB y Bluetooth.
