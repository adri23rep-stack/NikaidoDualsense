# Validación — Low Profile Alpha 2.3.3

## Validado en el entorno de entrega

- Compilación sintáctica de los archivos Python modificados.
- Arquitectura: `gui/main_window.py` permanece dentro del límite de tamaño y conserva sus dos clases públicas.
- Bandeja: estado Low Profile y callback de activación cubiertos por pruebas.
- Persistencia: el ajuste `low_profile_on_minimize` existe en valores predeterminados, Ajustes, Dashboard y asistente inicial.
- Ciclo de vida: la implementación conserva `QApplication`, destruye la ventana, desconecta callbacks, detiene timers y reconstruye una ventana nueva.
- La ruta HID de baja latencia de Alpha 2.3.2 no fue modificada.

## Pendiente

- Medición real de CPU y RAM en Windows con PySide6.
- Prueba física con DualSense, ViGEmBus y juego abierto.
- Confirmar USB y Bluetooth durante varios ciclos minimizar/reabrir.
