# Nikaido DualSense 2.9.8.1 Beta 1

## Objetivo

Pulir completamente la experiencia de perfiles antes del salto a Nikaido DualSense 3.0, conservando compatibilidad con perfiles, favoritos, reglas por juego y paquetes `.Nika` anteriores.

## Profile Studio 2.0

- Reemplaza la lista anterior por la vista híbrida elegida:
  - tarjetas visuales adaptables,
  - panel lateral de detalles,
  - búsqueda,
  - categorías,
  - favoritos,
  - ordenamiento,
  - acciones rápidas.
- Muestra de un vistazo:
  - L2 y R2,
  - vibración,
  - efecto RGB,
  - macros,
  - Input Studio,
  - procedencia de fábrica o personalizada.
- Incluye accesos directos a RGB Studio y Adaptive Trigger Studio.
- Mejora estados vacíos, filtros, selección, perfil activo y eliminación contextual.

## Iconos y animaciones

- Nuevo sistema de iconos vectoriales escalables sin depender de imágenes externas.
- Temas incluidos para shooter, precisión, arco, impacto, conducción, horror, RPG, sigilo, deportes, arcade y perfiles personalizados.
- Las imágenes elegidas por el usuario siguen teniendo prioridad.
- Los avatares y previews RGB se animan con un único reloj compartido.
- No se crea un temporizador por tarjeta.
- La opción **Reducir movimiento** disminuye la frecuencia y deja una vista estable.

## Editor de perfiles

- Descripción multilínea.
- Categorías sugeridas y editables.
- Galería de estilos visuales.
- Preview animado del avatar y del efecto RGB sin escribir al control.
- Biblioteca completa de presets de Trigger Studio dentro de L2 y R2.
- Copia rápida de L2 a R2 o de R2 a L2.
- Acción para dejar un gatillo libre.
- Conserva curvas multizona al cargar presets compatibles.

## Perfiles de fábrica reconstruidos

Los IDs anteriores se conservan para no romper configuraciones existentes, pero sus sensaciones, textos, identidad RGB e iconos fueron reconstruidos usando los presets compartidos de Trigger Studio.

Perfiles incluidos:

1. Shooter equilibrado
2. Precisión táctica
3. Arquería dinámica
4. Respuesta rápida
5. Impacto pesado
6. Cadencia alta
7. Potencia sostenida
8. Conducción precisa
9. Horror inmersivo
10. Control libre

## Seguridad y estabilidad

- El duplicado limpia imagen e Input Studio si la operación no puede completarse.
- Los perfiles de fábrica siguen protegidos contra eliminación o sobrescritura accidental.
- Las imágenes personalizadas continúan validadas y optimizadas antes de mostrarse o guardarse.
- Privacy Auditor distingue medios comprimidos de binarios genéricos para evitar falsos positivos por bytes aleatorios, sin dejar de bloquear rutas privadas reales.
- Se conserva el guardado atómico, respaldos y compatibilidad del formato `.Nika`.

## Validación

- 461 pruebas automatizadas aprobadas.
- 2 pruebas omitidas porque PySide6 no está instalado en el entorno de revisión.
- Compilación sintáctica completa de archivos Python aprobada.
- Privacy Auditor 2.0 aprobado.

## Límites de esta revisión

- No se realizó prueba física con un DualSense.
- No se compiló el ejecutable ni el instalador en Windows dentro de este entorno.
- Debe revisarse visualmente en Windows el escalado de 100 %, 125 % y 150 %, además del flujo completo de crear, editar, clonar, importar y eliminar perfiles.
