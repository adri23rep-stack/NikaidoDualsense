# Nikaido Input Studio

**Nikaido Input Studio** es la pantalla para ajustar las palancas fisicas y la salida del mando virtual. Se abre desde la pestana **Input Studio** de la aplicacion clasica o desde una interfaz personalizada mediante la accion `navigate.input_studio`.

## Uso

1. Elige el perfil que quieres editar. Al elegirlo tambien se activa, para que la vista en vivo sea exactamente la de ese perfil.
2. Escoge **Izquierda** o **Derecha** solo para decidir que palanca estas editando. La vista en vivo muestra siempre izquierda y derecha a la vez.
3. Ajusta los controles mientras observas los paneles **L fisica**, **L virtual**, **R fisica** y **R virtual**.
4. Los cambios quedan asociados al perfil y se restauran automaticamente cuando se vuelva a aplicar, incluidos los perfiles predefinidos.

La salida se calcula aunque la emulacion Xbox/DS4 este apagada para poder previsualizarla. Al activar una emulacion, ese mismo valor es el que se envia al mando virtual. Si Gyro Aim reemplaza el stick derecho, la vista **R virtual** muestra el valor final del gyro, no uno simulado.

## Vista en vivo

Cada panel muestra X, Y y magnitud (`M`) normalizadas de `-1.0` a `+1.0`.

| Panel | Que representa |
|---|---|
| L fisica / R fisica | Lectura cruda normalizada que llega desde el DualSense. |
| L virtual / R virtual | Resultado final que usara el mando virtual despues de deadzones, curva, drift, inversion, sensibilidad y gyro si aplica. |

Los aros ayudan a depurar ajustes: el aro interior marca la deadzone interior, el aro exterior discontinuo marca la deadzone exterior y el aro pequeno de anti-deadzone aparece cuando hay anti-deadzone configurado.

## Controles

| Control | Efecto |
|---|---|
| Deadzone interior | Ignora el movimiento alrededor del centro. Es radial, por lo que no deforma diagonales. |
| Deadzone exterior | Alcanza el maximo antes del borde fisico del stick. Util en palancas que no llegan al 100 %. |
| Anti-deadzone | Da un minimo de salida justo fuera de la zona muerta. Usar con moderacion. |
| Curva | `Lineal` conserva respuesta 1:1; `Exponencial` da mas precision cerca del centro; `Agresiva` responde antes; `Personalizada` interpola los puntos dibujados. |
| Sensibilidad X/Y | Modifica horizontal y vertical de forma independiente sin superar el rango permitido por el mando virtual. |
| Invertir X/Y | Invierte solo el eje seleccionado. |
| Correccion de drift | Resta el punto de reposo calibrado antes de procesar la zona muerta. |

## Calibrar drift

Pulsa **Calibrar reposo** con la palanca completamente suelta. La app recoge 120 reportes HID y guarda el promedio, por lo que no bloquea la interfaz ni fija como drift una lectura aislada. El progreso se muestra en la misma pantalla.

Cambiar de perfil cancela una calibracion que todavia no haya terminado. **Restablecer palanca** borra tambien su offset de drift, cancela el estado de calibracion de esa palanca y devuelve los valores predeterminados para el perfil actual.

## Persistencia y seguridad

Los datos se guardan en `settings.profile_input_studio` dentro de la configuracion normal de Nikaido. La migracion es compatible con configuraciones existentes: los perfiles sin datos reciben valores seguros por defecto. Los parametros se validan y limitan al cargar para impedir combinaciones de deadzones que provoquen divisiones por cero o una salida fuera de rango.
