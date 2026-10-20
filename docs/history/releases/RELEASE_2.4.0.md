# Nikaido DualSense 2.4.0 — Nikaido KeyBridge

## Nueva función: teclado y mouse como control virtual

Nikaido KeyBridge convierte entradas globales de teclado y mouse en un mando virtual completo mediante el mismo backend ViGEm de Nikaido. El usuario puede seleccionar Xbox 360 o DualShock 4 sin conectar un DualSense físico.

### Funciones principales

- Salida virtual Xbox 360 o DualShock 4.
- WASD o cualquier tecla para el stick izquierdo.
- Teclas o mouse para el stick derecho.
- Asignación editable para botones, cruceta, sticks, gatillos y botones de sistema.
- Gatillos analógicos con rampa configurable.
- Suavizado, sensibilidad, inversión y decaimiento del mouse.
- Normalización de diagonales.
- Frecuencia de lectura configurable entre 60 y 500 Hz.
- Atajo de pausa rápida, por defecto F8.
- Presets Shooter, Plataformas y Vacío.
- Configuración persistente y compatible con perfiles `.Nika`.
- Exclusión mutua con la entrada del DualSense físico para evitar dos escritores sobre ViGEm.
- Liberación automática de botones, sticks y gatillos al pausar, desactivar o cerrar Nikaido.

### Integración

La nueva página aparece dentro de Emulación bajo el nombre **Nikaido KeyBridge**. El motor reutiliza `EmulatorManager`, por lo que respeta el mismo selector DS4/Xbox, el cierre seguro y las comprobaciones de ViGEm existentes.

### Compatibilidad

Requiere Windows y el driver ViGEmBus. La captura global usa `GetAsyncKeyState`; no instala hooks persistentes ni modifica el teclado del sistema.
