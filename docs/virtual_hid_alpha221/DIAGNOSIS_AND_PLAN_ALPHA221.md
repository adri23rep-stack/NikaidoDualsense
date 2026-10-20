# Diagnóstico y plan — Alpha 2.2.1

## Procedencia e aislamiento

Alpha 2.2.1 parte de una copia completa de Alpha 2.2. El ZIP de esa base fue
verificado antes de copiarlo:

`3e98d6ec6f92d302d6472ff735b43fdb7053981139e4538b5172cc89c8881744`

La versión estable 2.9.8.9 conserva su identidad y SHA-256 declarado:

`14ea6788a36b620ec907a508c67e307aad8ccbec5a6235ba199e5e5910a29338`

El laboratorio permanece separado de la interfaz principal, de los sistemas de
emulación estables y de perfiles, configuraciones y archivos `.Nika`.

## Diagnóstico previo al código

La ejecución comunicada desde Windows confirmó:

- MSBuild, MSVC v145, WDK y SDK `10.0.28000.0` están disponibles.
- El kit 28000 contiene headers, bibliotecas, tareas de compilación e
  `InfVerif.exe` x64.
- El kit 28000 no contiene `Inf2Cat.exe`.
- `Inf2Cat.exe` sí existe en
  `Windows Kits\10\bin\10.0.26100.0\x86`.
- Alpha 2.2 buscaba `Inf2Cat` únicamente dentro del kit seleccionado y por eso
  clasificaba erróneamente el entorno como incompleto.

La causa es el detector de herramientas del laboratorio. Reinstalar o reparar
de nuevo el runtime, Visual Studio, SDK o WDK no corresponde a esta evidencia.

## Riesgos

1. Mezclar headers o bibliotecas de distintos kits podría producir un driver
   incoherente. Alpha 2.2.1 no lo permite.
2. Encontrar un ejecutable no demuestra que reconozca todos los identificadores
   `/os` solicitados. La ejecución real de `Inf2Cat` es el gate definitivo.
3. Reducir silenciosamente la lista de destinos produciría un catálogo con una
   cobertura distinta a la declarada. La lista permanece completa.
4. La salida de las herramientas puede revelar rutas privadas; se sanitiza
   antes de mostrarla.
5. Un catálogo sin firma no autoriza instalación o carga del driver.
6. La validación INF/CAT no demuestra enumeración HID ni estabilidad en kernel.

## Plan de Alpha 2.2.1

1. Mantener íntegramente el toolchain de compilación en el kit 28000.
2. Preferir `Inf2Cat` del mismo kit cuando esté disponible.
3. Si falta, buscar únicamente dentro de la misma raíz Windows Kits y aceptar
   como candidato una versión instalada desde el build 26100.
4. Preferir x64 y permitir x86 como fallback porque la herramienta procesa
   archivos del paquete y no forma parte del binario del driver.
5. Registrar por separado los kits y arquitecturas de compilación,
   `InfVerif` e `Inf2Cat`.
6. Ejecutar `Inf2Cat` con todos los destinos definidos; un código distinto de
   cero cancela el paquete y elimina el staging.
7. Añadir regresiones para la disposición observada `28000 + 26100 x86`,
   preferencia del mismo kit, rechazo de builds antiguos y manifiesto.
8. Ejecutar pruebas, compilación sintáctica, lint, simulador, privacidad y
   validación profunda del ZIP.

## Condición de salida

Alpha 2.2.1 estará lista para esta etapa cuando la copia de Windows encuentre
ambas herramientas y `PREPARE_VHF_ALPHA221_PACKAGE.bat` produzca un INF, SYS y
CAT con manifiesto, sin firma y sin instalar nada. Hasta recibir ese resultado
no se afirma que el kit 26100 acepte todos los destinos.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
