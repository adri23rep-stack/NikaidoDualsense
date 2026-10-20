# Diagnóstico y plan — Alpha 2.2.3

## Procedencia e aislamiento

Alpha 2.2.3 parte de una copia completa e independiente de Alpha 2.2.2. El ZIP
base fue verificado antes de copiarlo:

`56cb9ad6d910d4d21e85ddf9cc07303ff01005221dce2676f966975c8ce9b937`

La versión estable 2.9.8.9 mantiene su identidad:

`14ea6788a36b620ec907a508c67e307aad8ccbec5a6235ba199e5e5910a29338`

El laboratorio continúa separado de la interfaz principal, de la emulación
estable, de perfiles, configuraciones y archivos `.Nika`.

## Diagnóstico previo al código

La ejecución comunicada desde Windows demostró:

- El driver y el cliente compilaron con 0 advertencias y 0 errores.
- El build se produjo con el proyecto KMDF y el toolset oficial del WDK.
- El registro por hashes se bloqueó al inspeccionar el SYS.
- La única causa indicada fue la ausencia de `IMAGE_FILE_SYSTEM`.
- Al no existir un registro aprobado, el preparador se negó correctamente a
  continuar.
- No se creó, firmó, instaló ni cargó ningún paquete.

El defecto está en la validación local de Alpha 2.2.2. Se asumió que todo driver
KMDF debía contener el bit COFF `IMAGE_FILE_SYSTEM`. Microsoft documenta ese
bit como una descripción de archivo de sistema, pero no lo define como requisito
del linker `/DRIVER`.

La documentación oficial sí proporciona señales adecuadas para esta etapa:

- `IMAGE_FILE_EXECUTABLE_IMAGE` indica una imagen ejecutable válida.
- PE32+ y `IMAGE_FILE_MACHINE_AMD64` identifican una imagen x64.
- `IMAGE_SUBSYSTEM_NATIVE` corresponde a drivers y procesos nativos.
- `/DRIVER` es la opción que crea un driver de modo kernel.
- La ausencia de certificado incrustado es esperada antes de firmar.

Referencias:

- https://learn.microsoft.com/windows/win32/debug/pe-format
- https://learn.microsoft.com/cpp/build/reference/driver-windows-nt-kernel-mode-driver

No falta ningún componente de Visual Studio, SDK, WDK o Python. Reinstalarlos o
repararlos no corregiría esta regla.

## Riesgos

1. Quitar toda inspección permitiría aceptar un archivo cualquiera renombrado a
   `.sys`.
2. Exigir otro bit opcional del linker podría crear un nuevo falso bloqueo.
3. Aceptar una imagen no ejecutable ocultaría un build dañado.
4. La inspección PE local no sustituye `InfVerif`, `Inf2Cat`, firma ni carga.
5. Un registro anterior no debe sobrevivir a una compilación nueva o fallida.

## Plan de Alpha 2.2.3

1. Mantener el registro SHA-256 y su invalidación previa al build.
2. Retirar solamente el requisito obligatorio `IMAGE_FILE_SYSTEM`.
3. Exigir en su lugar:
   - cabeceras DOS y PE válidas;
   - arquitectura AMD64;
   - formato PE32+;
   - al menos una sección;
   - marca `IMAGE_FILE_EXECUTABLE_IMAGE`;
   - subsistema Native;
   - punto de entrada distinto de cero;
   - ausencia de certificado incrustado.
4. Aceptar tanto imágenes que tengan `IMAGE_FILE_SYSTEM` como las que no.
5. Conservar la validación del INF, `InfVerif`, `Inf2Cat`, hashes y staging
   transaccional.
6. Añadir regresiones que reproduzcan el SYS real del WDK sin el bit de sistema.
7. Mantener intactos `driver.c`, el protocolo VHF y la versión estable.
8. Ejecutar suite, lint, compilación sintáctica, simulador, privacidad y
   validación profunda del ZIP.

## Condición de salida

Alpha 2.2.3 debe crear el registro para una imagen PE32+ AMD64, ejecutable,
Native y sin firma aunque no tenga `IMAGE_FILE_SYSTEM`. Debe continuar
bloqueando imágenes no ejecutables, sin punto de entrada, con arquitectura o
subsistema incorrectos, dañadas o firmadas de forma inesperada.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
