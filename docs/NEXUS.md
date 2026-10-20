# Nikaido Nexus

Nikaido Nexus es la vista visual del remapeo avanzado. Usa directamente `AdvancedMapper`, las capas del perfil y el formato `.Nika`; no ejecuta un motor paralelo.

## Flujo recomendado

1. Selecciona el perfil.
2. Elige o crea una capa.
3. Selecciona una entrada en el DualSense visual.
4. Crea una acción y define el gesto.
5. Valida el mapa.
6. Prueba físicamente el control y guarda.

## Edición

Nexus permite:

- añadir, editar, duplicar y borrar acciones;
- copiar y pegar entre entradas;
- subir o bajar el orden de ejecución;
- buscar por nombre, destino, gesto o problema;
- deshacer y rehacer hasta 60 estados;
- ver las entradas presionadas en tiempo real;
- validar macros, perfiles, capas y destinos faltantes.

## Capas

Cada perfil puede tener hasta 32 capas. Es posible crear, duplicar, renombrar, eliminar y marcar la capa inicial. Nexus Flow muestra todas las capas, el número de acciones y cuál es la inicial.

Las capas temporales se apilan por orden de activación. Soltar modificadores en un orden diferente no debe dejar una capa pegada.

## Acciones y gestos

Acciones:

- control virtual;
- teclado;
- botones o movimiento de mouse;
- macro;
- perfil;
- capa;
- gyro;
- desactivar;
- conservar la entrada original.

Gestos:

- mantener;
- alternar;
- presionar;
- soltar;
- pulsación corta;
- pulsación larga;
- doble toque.

También admite turbo, bloqueo del botón original y hasta ocho botones requeridos como condición.

## Atajos

- `Ctrl+Z`: deshacer.
- `Ctrl+Y` o `Ctrl+Shift+Z`: rehacer.
- `Ctrl+C` / `Ctrl+V`: copiar y pegar.
- `Ctrl+D`: duplicar.
- `Supr`: eliminar.
- `Ctrl+F`: buscar.
- Flechas y `Enter`: recorrer el control visual.

## Compatibilidad y seguridad

- Máximo de 16 acciones por entrada y 256 caracteres por destino.
- Datos desconocidos se normalizan antes de llegar al tick HID.
- Las macros referenciadas se incluyen al exportar `.Nika`.
- Los IDs se remapean al importar para evitar choques.
