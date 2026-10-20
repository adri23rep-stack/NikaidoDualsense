# Nikaido DualSense 2.9.5.3

Hotfix del entorno de ejecución para la distribución de código fuente.

## Causa

`install.bat` instalaba `comtypes` y `pycaw` dentro de `.venv`, pero Windows podía abrir
`main.py` con el Python global mediante doble clic o un acceso antiguo. El motor de audio
se ejecutaba entonces en un intérprete diferente y reportaba que `comtypes` faltaba aunque
sí estuviera instalado en el entorno local.

## Cambios

- Nuevo `INICIAR_NIKAIDO.bat`, encargado de comprobar, reparar e iniciar con `.venv`.
- `main.py` cambia automáticamente al Python local antes de cargar dependencias externas.
- `install.bat` muestra y verifica el ejecutable real usado por Nikaido.
- `REPARAR_GUI_Y_AUDIO.bat` reinstala `comtypes` y `pycaw` sin caché.
- Los errores de Core Audio muestran la ruta exacta de `sys.executable`.
- Pruebas de regresión para selección del runtime, argumentos, bucles y scripts de inicio.

## Uso

Extraer el paquete y abrir `INICIAR_NIKAIDO.bat`. No es necesario abrir `main.py` ni
activar manualmente el entorno virtual.
