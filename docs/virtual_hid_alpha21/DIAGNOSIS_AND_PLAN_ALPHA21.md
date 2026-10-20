# Diagnóstico y plan — Alpha 2.1

## Evidencia recibida de Windows

El usuario ejecutó Alpha 2 en Windows x64 desde una consola de desarrollo. El
diagnóstico confirmó MSBuild 18.8.2, WDK y los archivos VHF. La compilación se
detuvo sin instalar nada y mostró dos causas distintas:

1. El driver no encontró `ntddk.h`. La línea de `cl.exe` no contenía las rutas
   de headers de kernel, lo que demuestra que encontrar `vhf.h` en disco no fue
   suficiente para integrar WDK con MSBuild.
2. El cliente solicitó `PlatformToolset=v143`, pero el entorno activo era
   Visual Studio 2026 con MSVC 14.51. Ese pin pertenecía a Visual Studio 2022.

No hubo evidencia de un fallo de enumeración, del protocolo VHF o de un
DualSense físico: la compilación terminó antes de generar un driver utilizable.

## Causas

- El comprobador de Alpha 2 validaba solo `vhf.h` y `VhfKm.lib`.
- No verificaba `ntddk.h`, los props de kernel ni el toolset
  `WindowsKernelModeDriver10.0` dentro de la instalación de Visual Studio.
- El cliente estaba fijado a `v143`.
- Los proyectos declaraban SDK `10.0` de forma genérica en vez de seleccionar el
  kit más reciente que MSBuild determinara como compatible.
- La solución identificaba Visual Studio 17 aunque se abrió con Visual Studio 18.

## Riesgos de driver y sistema

| Riesgo | Control de Alpha 2.1 | Estado |
| --- | --- | --- |
| Confundir un fallo de dependencias con código defectuoso | Gate previo y códigos de salida separados | Mitigado en fuente |
| Compilar contra SDK y WDK incompatibles | Se exige un conjunto completo de la familia 28000 | Mitigado en el gate |
| Generar un `.sys` no firmado | Mensaje de bloqueo y firma automática desactivada | Sigue bloqueado para instalar |
| Alterar protecciones de Windows | No existen comandos de BCD, instalación ni elevación | Prohibido por diseño |
| Colisión con la emulación estable | No se importa ni modifica ViGEmBus o HidHide | Aislado |
| Considerar la compilación como emulación funcional | Se documenta que enumeración y entrada real siguen sin verificar | Abierto |

## Plan ejecutado

1. Verificar los SHA-256 de la base estable, Alpha 1 y Alpha 2.
2. Crear una copia completa y separada de Alpha 2.
3. Actualizar únicamente identidad, archivos de proyecto, scripts de compilación,
   comprobador de toolchain, documentación y pruebas.
4. Mantener sin cambios la lógica del driver, el protocolo compartido, el
   simulador y los sistemas estables de emulación.
5. Añadir regresiones portables para entornos válidos e incompletos.
6. Ejecutar suite, compilación sintáctica, lint, privacidad y manifiesto.
7. Entregar fuente completa sin binarios ni certificados de driver.

## Confirmación de aislamiento

Alpha 2.1 no está integrada en PySide6 ni en el instalador principal. Sus
scripts no instalan drivers, no solicitan administrador y no cambian Secure
Boot, Integridad de memoria, HVCI o test signing. La base estable 2.9.8.9 y los
ZIP de Alpha 1 y Alpha 2 permanecen inmutables.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
