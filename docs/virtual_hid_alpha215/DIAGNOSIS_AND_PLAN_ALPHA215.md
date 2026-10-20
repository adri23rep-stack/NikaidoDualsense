# Diagnóstico y plan — Alpha 2.1.5

Fecha: 2026-07-22.

## Evidencia real de Windows

Alpha 2.1.4 produjo correctamente ambos artefactos Release x64:

- driver SHA-256:
  `56bb31026349e19d4711e93d69073d0e172fb897acbd1ef34c1456f6d004d4ad`;
- cliente SHA-256:
  `abe9a22e06cdb43fdec1bd64109ab6ca0662d6cc0d4e2dfb50e70f4e0d64f123`.

El comando `status` inició el cliente, no abrió ninguna interfaz y devolvió el
código de proceso `3`, que es correcto para ese estado. Sin embargo, el mensaje
mostró `error 0` y un carácter dañado en una palabra con acento. No se instaló,
cargó ni enumeró un driver.

## Causas

### Error Win32 perdido

`SetupDiEnumDeviceInterfaces`, `SetupDiGetDeviceInterfaceDetailW` o
`CreateFileW` podían fallar y establecer un error útil. El cliente llamaba
después a `SetupDiDestroyDeviceInfoList` y solo consultaba `GetLastError()` en
`wmain`. La limpieza podía reemplazar el error original por `ERROR_SUCCESS`.

### Unicode dependiente del entorno

El cliente usaba `wprintf`/`fwprintf`. Su conversión dependía de la configuración
del CRT y de la página de códigos de la consola, por lo que un literal Unicode
correcto podía mostrarse como un carácter de reemplazo.

## Corrección

1. Crear una copia independiente de Alpha 2.1.4.
2. Devolver handle y error mediante `OpenLabInterfaceResult`.
3. Capturar cada error inmediatamente, antes de limpiar SetupAPI.
4. Sustituir `ERROR_SUCCESS` por un fallback específico cuando una API falle
   sin proporcionar error.
5. Marcar respuestas de estado inválidas con `ERROR_INVALID_DATA`.
6. Usar `WriteConsoleW` para consola y UTF-8 explícito para redirección.
7. Añadir regresiones de orden de limpieza, error no nulo, Unicode y hash de
   `driver.c`.

## Resultado esperado en Windows

Sin driver instalado, `NikaidoVhfClient.exe status` debe:

- mostrar todos los acentos correctamente;
- indicar `error Win32 259` en el caso normal de lista sin interfaces, o algún
  otro error Win32 real distinto de cero si el entorno falla antes;
- devolver código de proceso `3`;
- no modificar Windows.

## Aislamiento

`driver.c` no cambia respecto a Alpha 2.1.4. Tampoco cambian el descriptor HID,
el protocolo, los IOCTL, el watchdog, la firma, la instalación o las
protecciones del sistema. La base estable 2.9.8.9 y todas las Alphas anteriores
permanecen intactas.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
