# Reporte del hotfix Nikaido DualSense 2.9.5.3

## Problema reportado

Después de ejecutar `install.bat`, el motor de audio seguía mostrando:

```text
RuntimeError: falta comtypes; ejecuta install.bat
```

## Causa real

La instalación sí colocaba `comtypes` y `pycaw` dentro del entorno local
`.venv`. Sin embargo, abrir `main.py` mediante doble clic, un acceso anterior o
`python main.py` podía usar el Python global. La instalación y la ejecución
ocurrían entonces en intérpretes diferentes.

## Reparaciones

1. **Nuevo `INICIAR_NIKAIDO.bat`**
   - Usa siempre `.venv\Scripts\python.exe`.
   - Comprueba las rutas reales de Python y `comtypes`.
   - Si el entorno está incompleto, reinstala `comtypes` y `pycaw` sin caché.
   - Después inicia `main.py` con el mismo intérprete validado.

2. **Cambio automático de runtime en `main.py`**
   - Antes de cargar Qt, HID o Core Audio, busca el entorno local.
   - Si Windows abrió el programa con otro Python, reemplaza el proceso por el
     ejecutable de `.venv` y conserva todos los argumentos.
   - Los EXE compilados y los procesos que ya usan `.venv` no se reinician.
   - Un marcador evita bucles de relanzamiento.

3. **Instalador y reparador más claros**
   - Muestran `sys.executable` y la ruta de `comtypes.__file__`.
   - Verifican GUI y audio usando el mismo Python que iniciará Nikaido.
   - La reparación fuerza una descarga limpia de Core Audio cuando el import
     falla.

4. **Compiladores alineados**
   - `COMPILAR_NIKAIDO.bat` y `CREAR_INSTALADOR.bat` dejaron de usar el Python
     global y ahora compilan desde `.venv`.

5. **Diagnóstico útil**
   - El error de audio incluye la ruta exacta del Python incorrecto y dirige al
     nuevo iniciador seguro.

## Uso recomendado

1. Extraer el ZIP en una carpeta nueva.
2. Ejecutar `INICIAR_NIKAIDO.bat`.
3. El iniciador creará o reparará `.venv` cuando sea necesario.

No es necesario activar manualmente el entorno ni escribir comandos.
