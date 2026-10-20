# Diagnóstico y plan — Alpha 2.2

## Procedencia e aislamiento

Alpha 2.2 parte de una copia completa de Alpha 2.1.5. El ZIP de esa base fue
verificado antes de copiarlo:

`57eee739ab9069ccb950f5895116f41c4f75efc887cf7d5821efb2558bb1b292`

La versión estable 2.9.8.9 conserva su identidad y SHA-256 declarado:

`14ea6788a36b620ec907a508c67e307aad8ccbec5a6235ba199e5e5910a29338`

Alpha 2.2 no se integra en la interfaz principal, no reutiliza los sistemas de
emulación estables y no modifica perfiles, configuraciones o archivos `.Nika`.

## Diagnóstico previo al código

La ejecución real comunicada para Alpha 2.1.5 demuestra únicamente lo
siguiente:

- MSBuild 18, MSVC v145 y WDK 28000 compilan el driver y el cliente sin
  advertencias ni errores.
- El cliente conserva el error Win32 y muestra Unicode correctamente.
- `ERROR_NO_MORE_ITEMS` (259) confirma que no hay una interfaz del laboratorio
  enumerada.
- No existe evidencia de instalación, carga, enumeración HID o compatibilidad
  con juegos.

El bloqueo inmediato no es una importación, el runtime de Python ni una
reinstalación general del WDK. Alpha 2.1.5 desactiva `Inf2Cat` deliberadamente
y no comprueba que `InfVerif.exe` o `Inf2Cat.exe` estén disponibles. Por ello,
el resultado compilado todavía no forma un paquete verificable para firma.

## Riesgos identificados

1. Un `.sys` compilado no es un paquete de driver.
2. Un catálogo generado por `Inf2Cat` todavía está sin firmar y no autoriza la
   carga del driver.
3. `InfVerif` requiere una ruta completa menor de 260 caracteres; una extracción
   demasiado profunda debe bloquearse con un diagnóstico concreto.
4. Los WDK pueden colocar `Inf2Cat` en `bin\\<versión>\\x64` o `x86`, mientras
   que `InfVerif` suele residir en `Tools\\x64`; asumir una sola ruta repetiría
   el fallo observado en Alpha 2.1.3.
5. La salida de herramientas del WDK puede contener rutas privadas. Los
   diagnósticos compartibles deben sustituirlas por marcadores neutros.
6. Un directorio parcial o un catálogo de una compilación anterior podría
   confundirse con un paquete válido si no se prepara de forma transaccional.
7. La validación del INF y del catálogo no demuestra estabilidad en kernel;
   todavía faltan firma aceptada, enumeración, Driver Verifier, HVCI y HLK.

## Plan de Alpha 2.2

1. Mantener `SignMode=Off` y `EnableInf2cat=false` durante MSBuild para separar
   claramente compilación y empaquetado.
2. Añadir un comprobador portable que distinga las herramientas de compilación
   de las herramientas de paquete.
3. Preparar únicamente una carpeta corta y controlada llamada
   `NikaidoVhfA22`, con el INF fuente y el `.sys` Release x64 recién compilado.
4. Validar que el binario sea PE x64, nativo y sin certificado Authenticode
   incrustado antes de copiarlo.
5. Ejecutar `InfVerif /u` porque el proyecto declara plataforma Universal.
6. Ejecutar `Inf2Cat` manualmente para los identificadores x64 documentados de
   Windows 10 y Windows 11, sin invocar `SignTool`.
7. Publicar fuera del paquete un manifiesto con tamaños, hashes y estados de
   validación, sin nombres de usuario, hostname ni rutas privadas.
8. Añadir regresiones portables para rutas de herramientas, validación PE,
   limpieza segura, manifiesto y ausencia de acciones de instalación.
9. Ejecutar la suite completa, compilación sintáctica, lint, autoprueba,
   auditoría de privacidad y validación profunda del ZIP.

## Condición de salida

Alpha 2.2 estará completa cuando pueda producir en Windows una carpeta con
`NikaidoVirtualHid.inf`, `NikaidoVirtualHid.sys` y
`NikaidoVirtualHid.cat`, y tanto `InfVerif` como `Inf2Cat` terminen con código
cero. El catálogo seguirá explícitamente sin firma; instalar o cargar cualquier
resultado continuará bloqueado.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
