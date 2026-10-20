# Reporte — Nikaido DualSense 2.7.1

**Base usada:** Nikaido DualSense 2.7.0 Mascot Wizard Foundation  
**Objetivo:** corregir el estado falso de conexión después de desconectar físicamente el DualSense.

## Causa encontrada

`pydualsense` puede conservar en memoria el último estado y el último arreglo de bytes después de retirar el USB o perder Bluetooth. El lector de Nikaido interpretaba esa fotografía congelada como una lectura correcta y renovaba continuamente el tiempo de conexión.

## Corrección aplicada

- Nikaido ahora comprueba que el contador del reporte HID realmente avance.
- Repetir el mismo reporte durante sondeos normales sigue permitido.
- Si no llega un reporte nuevo durante 1.5 segundos, la conexión se declara perdida.
- Si la fuente de reportes crudos existe pero deja de producir una captura válida, tampoco se usa el estado viejo como prueba de vida.
- Al desconectar se crea una fotografía neutral nueva:
  - batería 0 / desconocida
  - botones liberados
  - sticks centrados
  - gatillos en cero
  - touchpad y sensores limpios
  - tipo de conexión `NONE`
- Se informa inmediatamente a la interfaz del estado desconectado.
- Se liberan todas las entradas virtuales para evitar botones o palancas pegadas.
- La batería visual cambia a `—` en vez de conservar el porcentaje anterior.
- El wizard vuelve automáticamente a “Buscando DualSense…” y recupera la pose de conexión de Nikaido.

## Validación

- 287 pruebas aprobadas.
- 5 regresiones nuevas específicas para desconexión.
- Compilación de `main.py`, `src`, `gui` y `tests` correcta.
- Versiones sincronizadas en Python, `pyproject.toml` e Inno Setup.

## Prueba física recomendada

1. Conectar por USB y esperar a que Dashboard/Wizard indiquen conexión.
2. Retirar el cable sin cerrar Nikaido.
3. Confirmar que en aproximadamente 1.5 segundos cambia a “Buscando”.
4. Repetir por Bluetooth apagando el control o alejándolo.
5. Confirmar que ningún botón, stick o motor virtual queda activo.
