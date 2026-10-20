# Nikaido DualSense 2.0.2 — Sidebar y giroscopio DS4

## Qué se corrigió

### Barra lateral

El hotfix 2.0.1 corrigió el estilo de `QTabWidget`, pero la captura del usuario mostró que el componente roto era la barra lateral de navegación. En 2.0.2:

- el viewport y el contenido del scroll usan explícitamente el color oscuro de Nikaido;
- el ancho pasa de 248 a 292 px;
- títulos y subtítulos se almacenan por separado;
- los botones con descripción tienen 58 px de alto;
- desaparecen los textos cortados y el fondo gris del sistema.

### Passthrough DS4

El primer centrado automático podía aceptar un giro uniforme como si fuera el punto de reposo. Al soltar el mando, ese valor se restaba y aparecía una rotación en sentido contrario. En 2.0.2:

- la ventana de reposo aumenta de 24 a 48 muestras;
- el límite de estabilidad es más estricto;
- un centro inicial incorrecto puede reemplazarse por un candidato claramente mejor;
- la adaptación térmica solo ocurre cerca del cero y ya no aprende giros sostenidos;
- mientras se confirma la recuperación, el reporte se mantiene neutral para evitar el giro contrario;
- se aplica una zona de ruido radial pequeña después del centrado.

## Compatibilidad

No cambia el formato `.Nika`, la versión de configuración ni los signos configurables de los ejes. Perfiles, macros, calibraciones y ajustes anteriores siguen siendo compatibles.

## Validación

- 99 pruebas aprobadas.
- Prueba nueva que reproduce el drift contrario después de activar el modo mientras el mando se mueve.
- Prueba nueva que confirma que un giro sostenido no se aprende como drift térmico.
- Compilación de todos los módulos Python sin errores.
