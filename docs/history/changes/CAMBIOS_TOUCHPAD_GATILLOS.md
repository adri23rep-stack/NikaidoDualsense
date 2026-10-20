# Touchpad como mouse y gatillos multizona

## Touchpad como mouse

- Se instancia desde `main.py` y queda conectado a las lecturas reales de `ConnectionManager`.
- Nuevo panel en **Configuración > Touchpad como mouse**.
- Switch de activación y sensibilidad de `0.1x` a `10.0x`.
- El movimiento es relativo, por lo que no salta a una posición absoluta de la pantalla.
- El clic físico del touchpad funciona como clic izquierdo.
- Filtra saltos anormales del sensor y libera el botón al desactivar o cerrar la app.
- La activación y sensibilidad se guardan en `profiles.json`.

## Curva de gatillo multizona real

- Los cuatro puntos del editor ahora representan cuatro tramos independientes.
- Cada tramo se expande a las 10 zonas físicas del gatillo.
- Las fuerzas se convierten de la escala visual `0-255` a la escala real `0-8`.
- El efecto usa el modo Feedback `0x21`.
- Se empaquetan las zonas activas y las diez fuerzas en los seis bytes admitidos por `pydualsense`.
- La interfaz muestra la fuerza final enviada a cada zona, de la 0 a la 9.
- Los puntos no pueden cruzarse ni compartir posición, evitando curvas inválidas.
- Al cambiar de efecto se limpian los siete parámetros anteriores para impedir residuos hápticos.

## Pruebas incluidas

Ejecutar desde la raíz del proyecto:

```cmd
python tools\test_touchpad_multizone.py
```

La prueba valida sin hardware:

- Conversión de cuatro tramos a diez zonas.
- Empaquetado y desempaquetado de fuerzas.
- Modo de efecto `0x21`.
- Escritura de los siete parámetros de `pydualsense`.
- Movimiento, clic y liberación segura del mouse.

## Prueba manual recomendada en Windows

1. Abre **Configuración > Touchpad como mouse** y activa el switch.
2. Mueve un dedo por el touchpad y ajusta la sensibilidad.
3. Presiona físicamente el touchpad para comprobar el clic izquierdo.
4. En **Gatillos**, mueve los cuatro puntos y revisa la línea de fuerzas por zona.
5. Prueba primero con fuerzas medias. Después sube cada tramo por separado para confirmar que la resistencia cambia durante el recorrido.

La lógica y las pruebas simuladas están completas. La sensación física final todavía debe comprobarse con un DualSense real en Windows, porque los gatillos, como casi todo hardware caprichoso, se reservan el derecho de opinar.
