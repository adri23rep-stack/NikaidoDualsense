# Mapper avanzado: capas y gestos

La sección **Mapper** tiene dos niveles:

- **Remapeo directo:** cambia un botón físico por otro de forma simple.
- **Capas y gestos:** crea reglas avanzadas guardadas por perfil.

El motor avanzado procesa el mismo paquete físico que recibe ViGEm. No modifica la lectura original: decide qué salida adicional se genera y si el botón físico debe llegar al control virtual.

## Acciones disponibles

| Acción | Destino |
|---|---|
| Botón virtual | `cross`, `R1`, `dpad_up`, etc. |
| Teclado | `F`, `SPACE`, `CTRL+SHIFT+F`, `ALT+TAB` |
| Botón del mouse | `left`, `right`, `middle`, `x1`, `x2` |
| Movimiento del mouse | delta `dx,dy`, por ejemplo `30,-15` |
| Macro | una macro existente |
| Cambiar perfil | un perfil disponible |
| Cambiar capa | una capa creada en el editor |
| Giroscopio | recentrar, activar, apagar o alternar |
| Desactivar botón | bloquea la entrada física |
| Passthrough | deja pasar la entrada sin modificarla |

La salida de teclado y mouse necesita Windows y `pywin32`. Las acciones de control virtual requieren emulación Xbox 360 o PlayStation 4.

## Gestos

- **Mientras se mantiene:** activa al presionar y libera al soltar.
- **Al presionar:** genera un pulso al bajar el botón.
- **Al soltar:** genera un pulso al levantarlo.
- **Pulsación corta:** se dispara al soltar antes del umbral de larga.
- **Pulsación larga:** se activa después del tiempo configurado y se libera al soltar.
- **Doble pulsación:** se ejecuta al segundo toque dentro de la ventana elegida.
- **Alternar:** la primera pulsación activa y la siguiente desactiva.

### Doble pulsación exclusiva

Al activar **Reservar la doble pulsación**, Nikaido espera brevemente antes de ejecutar las acciones simples del mismo botón. Si llega el segundo toque, cancela las simples y ejecuta solamente la doble. Esto evita abrir el mapa y recentrar el gyro al mismo tiempo, por ejemplo.

## Condiciones y combos

Una regla puede exigir que otros botones estén presionados. Una acción de `X` con requisito `L1` funciona como `L1 + X`.

Los cambios de capa se procesan antes que los demás botones del mismo reporte HID. Por eso una combinación puede entrar a la capa nueva y usarla desde el primer paquete, sin un frame de retraso.

## Capas

- `base` siempre existe y no puede eliminarse.
- una capa secundaria hereda los botones de `base` cuando no define reglas propias para ellos;
- **Cambiar capa + Mantener** vuelve a la capa anterior al soltar;
- **Cambiar capa + Alternar** conserva la capa hasta pulsar de nuevo;
- los modificadores de capa pueden soltarse en cualquier orden; la capa activa más reciente se conserva hasta que su botón también se libere;
- renombrar una capa actualiza automáticamente las reglas que apuntaban a ella;
- eliminar una capa desactiva referencias que ya no tienen destino.

## Perfiles

Cada perfil puede tener su propio mapa avanzado. Cuando una acción cambia de perfil, el nuevo mapa se instala al terminar el gesto físico actual. Esto evita perder el evento de liberación y dejar una tecla, capa o botón virtual pegado.

El mapa global usado por Nikaido 2.0 se conserva como respaldo de migración para perfiles sin reglas propias.

## Guardado en `.Nika`

Las capas y reglas viajan dentro del campo `advanced_mapping` de `profile.json`. El formato `.Nika` continúa en versión 1 porque agregar este campo no rompe importadores anteriores.

## Recomendaciones

- usa remapeo directo para cambios uno-a-uno;
- usa capas solo cuando una misma entrada necesite varias funciones;
- evita dos reglas que bloqueen y dejen pasar el mismo botón al mismo tiempo;
- prueba primero con el Centro de diagnóstico abierto para confirmar la capa activa y los botones bloqueados.
