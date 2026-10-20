# Nikaido DualSense 2.9.7.0 — RGB Studio completo

## Objetivo

Rediseñar únicamente la pestaña existente **Luces RGB y efectos** sin crear una
sección paralela ni reemplazar la navegación general de Nikaido DualSense.

## Interfaz

- Vista previa vectorial del DualSense al centro.
- Barra RGB alrededor del touchpad y barra superior animadas en tiempo real.
- Un solo reloj de vista previa compartido por el control, el icono activo, la
  galería y la línea de tiempo. Las tarjetas no crean temporizadores separados.
- Reproducción, pausa y reinicio de la vista previa.
- Galería filtrable por efectos básicos, animados, temáticos y reactivos.
- Línea de tiempo con color, curva de brillo y cabezal de reproducción.
- Paletas rápidas: Nikaido, Vaporwave, Océano, Fuego e Hielo.
- Controles de velocidad, brillo, intensidad, suavizado, dirección y
  sensibilidad de audio.
- Los ajustes nuevos también están disponibles en el editor de perfiles.

## Efectos incluidos

1. Color fijo
2. Respiración
3. Pulso
4. RGB arcoíris
5. Ola neón
6. Cometa
7. Latido
8. Aurora
9. Plasma
10. Fuego
11. Hielo
12. Alerta roja y azul
13. Audio reactivo
14. Animaciones personalizadas por paleta

## Motor RGB

- El motor físico y la vista previa comparten `sample_light_effect`; no existen
  dos algoritmos distintos para un mismo efecto.
- Configuración compatible con perfiles anteriores. Los campos ausentes se
  completan con valores seguros.
- Suavizado temporal para reducir cambios bruscos y tráfico HID innecesario.
- El efecto de audio usa el medidor del dispositivo de salida predeterminado de
  Windows mediante pycaw/comtypes.
- El medidor de audio es opcional y sus errores quedan aislados; no bloquean el
  control ni detienen otras animaciones.
- La interfaz usa una simulación claramente marcada cuando no puede leer audio
  real, mientras que el motor físico no inventa nivel de audio.

## Iconografía

- Se añadieron 13 PNG transparentes en `assets/rgb_icons`.
- La interfaz dibuja versiones vectoriales animadas inspiradas en esos iconos,
  para conservar nitidez en cualquier escala y evitar cargar trece animaciones
  raster independientes.

## Limitación física importante

El DualSense permite enviar un color RGB global a la barra de luz. La vista
central representa movimiento, dirección y cola de forma visual, pero el mando
físico reproduce estos conceptos cambiando su color y brillo a lo largo del
tiempo; no tiene zonas RGB direccionables independientes.

## Validación realizada

- Compilación sintáctica de `gui` y `src`.
- Pruebas de todos los efectos y sus segmentos visuales.
- Pruebas de compatibilidad con perfiles antiguos.
- Prueba del audio reactivo con proveedor de nivel inyectado.
- Pruebas de concurrencia del único trabajador de luces.
- Suite completa: **434 pruebas aprobadas y 2 omitidas** por no estar PySide6
  instalado en el entorno de validación.

## No validado físicamente

- No se conectó un DualSense real en este entorno.
- No se abrió la interfaz Qt renderizada porque PySide6 no estaba instalado en
  el entorno de validación; la estructura fuente y el arranque de módulos sí se
  validaron mediante compilación y pruebas automatizadas.
