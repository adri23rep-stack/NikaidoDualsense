# Mascota de Nikaido — base 2.7

## Recursos

Los sprites viven en `assets/mascot` y se empaquetan junto con el resto de `assets`.

- `poses_a`: cuerpo completo, pensado para wizard, presentaciones y eventos grandes.
- `poses_b`: medio cuerpo, preparado para Dashboard, avisos, consejos y errores.
- `manifest.json`: nombres normalizados y rutas de todos los sprites.

Los archivos usan PNG RGBA real. Las rutas no contienen acentos ni espacios para reducir problemas en builds de Windows.

## Componente

`gui.components.MascotPanel` recibe:

- pose
- título
- mensaje
- insignia contextual

El componente conserva el `QPixmap` original y lo vuelve a escalar cuando cambia el tamaño, usando suavizado.

## Uso actual

El wizard utiliza seis escenas:

1. `greeting`
2. `present_left`
3. `point_left`
4. `thinking`
5. `happy`
6. `celebrating`

La pantalla de conexión puede cambiar temporalmente a `happy` cuando detecta el DualSense.

## Uso futuro recomendado

Las poses compactas ya están listas para:

- conexión
- batería baja
- error leve
- error grave
- actualización
- consejos contextuales
- estado inactivo
