# Prioridades oficiales de Nikaido DualSense

Esta lista ordena el desarrollo por impacto real en estabilidad, experiencia de uso y valor para el usuario. La regla es no añadir una función nueva hasta que la anterior sea confiable y fácil de probar.

## 1. Centro de diagnóstico profesional — Implementado en 2.1

Objetivo: encontrar problemas de conexión, latencia o doble entrada sin adivinar.

Incluye:

- frecuencia del DualSense físico y del control virtual;
- latencia promedio, picos p95 y tiempo de cada tramo de procesamiento;
- paquetes repetidos, perdidos y origen de la lectura;
- valores crudos de sticks, gatillos, botones, giroscopio y acelerómetro;
- consumo de RAM, CPU e hilos;
- detección de programas que pueden duplicar la entrada;
- capturas de 10, 20 o 30 segundos;
- reporte ZIP sanitizado sin rutas personales, contenido de macros ni archivos de perfiles.

Criterio de calidad: el diagnóstico nunca escribe en HID o ViGEm y observa como máximo a 60 Hz para no meter retraso en el control.

## 2. Modos avanzados de botones y capas — Implementado en 2.1

Objetivo: permitir configuraciones potentes sin llenar el programa de reglas difíciles de entender.

Incluye:

- pulsar, mantener, soltar, pulsación corta, larga, doble y alternar;
- reserva de doble pulsación para evitar que también se dispare la acción simple;
- acciones de control virtual, teclado, mouse, macro, perfil, capa y giroscopio;
- condiciones como `L1 + X`;
- turbo configurable;
- bloqueo o passthrough de la entrada original;
- capas heredables con una capa base;
- cambios temporales de capa o perfil mientras se mantiene un botón;
- apilado seguro de capas para soltar modificadores en cualquier orden;
- editor visual para crear, editar, duplicar y eliminar reglas;
- configuración separada por perfil y guardada dentro de `.Nika`.

Criterio de calidad: las capas se resuelven antes que los demás botones del mismo paquete físico y los cambios de perfil esperan a que termine el gesto para no dejar teclas o capas pegadas.

## 3. Gyro Aim avanzado y Flick Stick — Implementado en 2.1

Objetivo: convertir el giroscopio en una alternativa real al mouse o al stick derecho.

Incluye:

- salida como mouse, stick derecho o passthrough DS4;
- activación permanente, al mantener L2, con cualquier botón, touchpad, alternar o invertida;
- sensibilidad horizontal y vertical separadas;
- zona muerta, suavizado, aceleración, límite de velocidad y filtro de drift;
- mezcla con el stick físico: sumar, reemplazar o priorizar gyro;
- curvas lineal, exponencial y de precisión;
- presets Suave, Equilibrado, Competitivo y Gyro como stick;
- Flick Stick con umbral, liberación, ángulo mínimo y giro continuo;
- calibración del giro por mouse en píxeles por grado;
- calibración del giro por stick mediante tiempo para 180 grados;
- telemetría en vivo y ajustes por perfil;
- Mouse → Gyro opcional, apagado por defecto.

Criterio de calidad: Flick Stick reutiliza y neutraliza la palanca derecha únicamente mientras está activo, sin alterar el passthrough DS4 que ya funciona.

## 4. Overlay dentro de los juegos

Mostrar durante unos segundos el perfil, capa, estado del gyro, macro, batería y tipo de emulación. Debe ser discreto, opcional y no capturar clics.

## 5. Actualizador con restauración

Canales estable y experimental, copia de perfiles, verificación del paquete y regreso a la versión anterior si algo falla.

## 6. Compatibilidad con varios controles

Perfiles, calibración, color, emulación y diagnóstico independientes para cada DualSense conectado.

## 7. Biblioteca comunitaria de perfiles

Vista previa segura, autor, versión, categorías, instalación con un clic y actualización sin borrar cambios personales.

## 8. Importadores de otros programas

Importación gradual de botones, curvas y zonas muertas desde configuraciones compatibles de otras herramientas, sin prometer funciones que no puedan traducirse de forma confiable.

## 9. Modo portátil

Ejecutar Nikaido desde una carpeta, con configuración local y sin modificar el sistema más de lo necesario.

## 10. API de extensiones

Efectos RGB, acciones de macros e integraciones externas mediante una API versionada. Se deja al final para evitar una base difícil de mantener.
