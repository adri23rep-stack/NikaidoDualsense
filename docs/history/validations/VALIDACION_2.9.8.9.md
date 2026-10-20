# Validación Nikaido DualSense 2.9.8.9 Beta 1

## Línea base y revisión completa

- ZIP original seguro: 406 archivos, sin rutas absolutas, traversal, enlaces
  simbólicos ni entradas duplicadas.
- SHA-256 del ZIP recibido:
  `78a67c84986431fbc545c4f5d62c93965e7b5ffdb6381ddf421da7a6cfe4a78d`.
- Proyecto revisado: 162 archivos Python y 62,793 líneas Python antes de los
  cambios.
- Compilación sintáctica inicial: 162/162.
- Importación inicial de módulos principales: 66/66.
- Suite inicial: 500 pruebas aprobadas en 7.04 s.
- No se detectaron importaciones locales sin resolver ni definiciones
  duplicadas. El único ciclo estático encontrado corresponde a exports y
  referencias de tipado de la interfaz; no produjo un ciclo de importación en
  ejecución.

## Reproducción del ciclo de vida

Con una sola `QApplication`, un `ConnectionManager` y un `TriggerEngine`
compartidos, la versión original produjo después de tres construcciones/cierres:

- Ventanas Python aún vivas: 1, 2 y 3.
- Widgets Qt de nivel superior: 10, 20 y 30.
- Callbacks de la ventana acumulados en conexión, batería, estado, error y
  cambio de perfil.

Después de la corrección, en tres ciclos consecutivos abriendo Profile Studio:

- Todos los conteos de callbacks vuelven a la línea base en cada cierre.
- Ventanas Python vivas después de cada cierre: 0.
- Widgets Qt de nivel superior después de cada cierre: 0.

## Automatización final

- Suite completa sobre la copia final: **510 pruebas aprobadas, 0 fallos, 0 omitidas**, 7.98 s.
- Regresiones nuevas: **10 aprobadas**.
- Compilación sintáctica final: **164/164 archivos Python**, 0 errores.
- Ruff sobre el código activo (excluyendo la interfaz heredada): 0 hallazgos.
- Módulos principales importados sin backend gráfico de bandeja: **66/66**.
- Checker independiente de dependencias: aprobado en el entorno disponible.
- PySide6 real 6.8.3 con `QT_QPA_PLATFORM=offscreen`.
- Profile Studio construido y abierto en los tres ciclos.
- Botones reales de Nuevo perfil y Editar perfil cubiertos por la suite; una
  excepción inyectada en el editor se registra y se presenta como error visible.
- Ocho perfiles incluidos aplicados sin hardware:
  `assault_rifle`, `racing`, `horror`, `lmg`, `pistol`, `shotgun`, `off`, `bow`.
- Importación/exportación `.Nika`, formato JSON anterior, migración, iconos y
  banners cubiertos por las pruebas heredadas.
- Dashboard validado con imagen ausente, ruta inexistente, icono temático y
  contenido de imagen corrupto.

## Casos que no se ejecutaron

- Entrada/salida física con un DualSense.
- USB, Bluetooth, audio Core Audio, ViGEm, HidHide y bandeja real de Windows.
- Primer/segundo arranque como procesos Windows separados; el equivalente Qt
  se ejecutó como tres ciclos completos en una misma `QApplication` offscreen.
- Compilación Nuitka, firma, Inno Setup e instalación en Windows.

## Resultado

No quedan fallos conocidos dentro del entorno automatizado probado. Los puntos
anteriores son limitaciones de entorno, no pruebas aprobadas ni afirmaciones de
funcionamiento físico.

© Team Nikaido
