# Reporte — Nikaido DualSense 2.7.2

**Base usada:** Nikaido DualSense 2.7.1 Disconnect Detection Hotfix  
**Objetivo:** reducir RAM y trabajo innecesario sin alterar funciones.

## Hallazgos principales

1. El wizard se ocultaba al aceptar, pero no garantizaba la destrucción de todo el árbol Qt.
2. El estado de conexión podía volver a cargar la misma pose de Nikaido varias veces por segundo.
3. Los PNG se decodificaban a resolución completa antes de reducirlos para la interfaz.
4. Un fondo grande podía existir simultáneamente en la ventana principal y en la vista previa del wizard.
5. Todas las clases de páginas se importaban desde el arranque aunque sus widgets ya fueran diferidos.
6. Diagnóstico declaraba 60 Hz, pero construía una muestra anidada en cada callback HID.

## Cambios aplicados

### Wizard y mascota

- `WA_DeleteOnClose` activado.
- Liberación explícita de sprites, fondo y temporizador al finalizar.
- El temporizador de conexión solo funciona durante el paso Conexión.
- `MascotPanel` recuerda la pose actual y evita recargarla si no cambió.
- Decodificación limitada a 440×560 para poses completas y 420×420 para compactas.

### Imágenes

- Fondos principales limitados a una decodificación máxima de 2560×1600.
- Vista previa de apariencia limitada a 640×440.
- Miniaturas de perfiles usan `QImageReader` y se decodifican directamente cerca de 92×92 o del tamaño solicitado.
- Caché global de Qt limitado a 8192 KB.

### Carga diferida

- `profiles`, `system`, `nexus`, `input`, `macros`, `device` y `settings` se importan mediante `importlib` únicamente cuando se abre una pantalla que los necesita.
- El wizard también se importa solo cuando realmente se va a mostrar.

### Diagnóstico

- Historial pasivo reducido de 35 a 10 segundos, que es exactamente lo adjuntado en reportes.
- Muestreo pasivo limitado a 60 Hz.
- Las capturas iniciadas manualmente conservan el comportamiento existente.

## Validación

- 292 pruebas aprobadas.
- `compileall` correcto.
- Versiones sincronizadas en Python, `pyproject.toml` e Inno Setup.
- No fue posible medir el RSS real de Windows/PySide6 en este entorno; la comparación final debe hacerse en el equipo del usuario.
