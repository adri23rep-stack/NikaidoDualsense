# Diagnóstico y plan — Alpha 2.2.2

## Procedencia e aislamiento

Alpha 2.2.2 parte de una copia completa de Alpha 2.2.1. El ZIP fue verificado
antes de copiarlo:

`f9148decb8c23e83f13563a456ecc518f703194602197b4ca5f0e0e72eccc9e6`

La versión estable 2.9.8.9 conserva su identidad:

`14ea6788a36b620ec907a508c67e307aad8ccbec5a6235ba199e5e5910a29338`

El laboratorio continúa separado de la interfaz principal, los sistemas de
emulación estables, perfiles, configuraciones y archivos `.Nika`.

## Diagnóstico previo al código

La ejecución comunicada desde Windows demostró:

- Driver y cliente compilaron con 0 advertencias y 0 errores.
- El toolchain 28000 y las bibliotecas Spectre están completos.
- `InfVerif` 28000 x64 e `Inf2Cat` 26100 x86 fueron detectados correctamente.
- Inmediatamente después del build, el preparador afirmó que el SYS era
  anterior a una fuente.
- El bloqueo ocurrió antes de ejecutar `InfVerif` o `Inf2Cat`.
- No se publicó, firmó, instaló ni cargó ningún paquete.

La causa es el control de frescura de Alpha 2.2.1: comparaba marcas de tiempo
del SYS con las fuentes. Los ZIP no conservan zona horaria y fecha con la misma
semántica en todos los sistemas; una fuente extraída puede aparecer en el
futuro aunque el SYS se haya generado después. Recompilar no puede corregir esa
comparación.

No faltan componentes de Visual Studio, SDK, WDK o Python. Repararlos o
reinstalarlos sería innecesario.

## Riesgos

1. Eliminar la comprobación permitiría empaquetar un SYS viejo.
2. Confiar solo en la existencia del archivo no vincula el SYS con las fuentes.
3. Conservar un comprobante de un build anterior permitiría reutilizarlo tras
   una compilación fallida.
4. Un registro con rutas absolutas filtraría información privada.
5. El registro no sustituye la validación PE, `InfVerif`, `Inf2Cat` o firma.

## Plan de Alpha 2.2.2

1. Eliminar únicamente el registro generado antes de iniciar MSBuild.
2. Compilar driver y cliente como etapas separadas.
3. Crear un registro solamente si ambas etapas terminan con código cero.
4. Guardar rutas relativas, tamaños y SHA-256 del SYS y de:
   - `driver.c`;
   - protocolo VHF;
   - proyecto del driver;
   - INF fuente.
5. En el preparador, exigir identidad, versión, conjunto exacto de entradas y
   coincidencia de todos los hashes.
6. Ignorar por completo fechas del ZIP, zona horaria y reloj.
7. Mantener validación PE, staging transaccional, `InfVerif`, `Inf2Cat`,
   sanitización y separación de kits.
8. Añadir regresiones para fechas futuras, registro ausente, fuente cambiada,
   SYS cambiado, privacidad y limpieza controlada.
9. Ejecutar suite, compilación sintáctica, lint, simulador, privacidad y
   validación profunda del ZIP.

## Condición de salida

Alpha 2.2.2 resolverá este defecto si un conjunto de fuentes con fechas futuras
puede preparar el paquete cuando sus hashes coinciden, pero bloquea cualquier
cambio posterior. La ejecución real de `InfVerif` e `Inf2Cat` seguirá pendiente
hasta probar esta copia en Windows.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
