# Nikaido DualSense 1.2 — perfiles, luces y gatillos

## Perfiles completos

Los perfiles personales ya no guardan solamente la vibración. Ahora pueden conservar:

- Imagen elegida desde el equipo.
- Efecto, rigidez, zonas, frecuencia, animación y curva de L2 y R2.
- Intensidad de vibración general y vibración adicional de cada gatillo.
- Efecto de luces, colores, velocidad, brillo y paleta.
- Macros activadas o desactivadas.
- Configuración completa de Nikaido Input Studio.

Los perfiles antiguos siguen cargando; los campos nuevos reciben valores seguros cuando no existen.

## Imágenes de perfil

Al crear o editar un perfil se puede elegir PNG, JPG, JPEG, WEBP o BMP. Nikaido copia la imagen a su carpeta de datos para que el perfil no dependa del archivo original. Al exportar un perfil, la imagen se incluye dentro del JSON y se recupera al importarlo en otro equipo.

## Luces y efectos

La sección Luces ahora incluye:

- Color fijo.
- Arcoíris RGB.
- Ola entre dos colores.
- Respiración.
- Pulso.
- Paletas personalizadas.
- Guardado y borrado de animaciones propias.

Los efectos se ejecutan sin bloquear la interfaz y se restauran al conectar nuevamente el control.

## Gatillos restaurados

La sección Vibración vuelve a mostrar los ajustes completos de ambos gatillos:

- Tipo de efecto.
- Rigidez o intensidad.
- Zona inicial y final.
- Frecuencia.
- Animación y velocidad.
- Curva visual editable con cuatro puntos.

La curva se guarda por perfil y por gatillo.

## Corrección del bloqueo de perfiles

La aplicación ya no destruye y reconstruye la cuadrícula de perfiles durante el mismo clic que aplica uno. Las actualizaciones se agrupan y se ejecutan después de terminar el evento actual, evitando el bloqueo o cierre que podía aparecer en el primer intento.

## Compatibilidad y pruebas

- Se conservaron las funciones anteriores del motor de gatillos.
- Se agregó el motor de luces al empaquetado de PyInstaller.
- Se añadieron pruebas de perfiles completos, imágenes, Input Studio y efectos de luz.
- Resultado actual: 47 pruebas aprobadas.
