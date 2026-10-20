# Diagnóstico y plan — Alpha 2

## Procedencia y aislamiento

La base oficial estable 2.9.8.9 se mantuvo inmutable. Alpha 2 se creó desde una
copia independiente del ZIP final de Alpha 1, cuyo SHA-256 volvió a coincidir:

`5592243217e3659314bf06905d013096d8c77d0fb4b4b8e16756fcd6b15b0378`

El manifiesto heredado de la versión estable conserva 411/411 hashes correctos.
El laboratorio no se integra en `main.py`, `src`, `gui` ni el instalador; tampoco
importa o reemplaza ViGEmBus, HidHide o los sistemas de emulación existentes.

## Diagnóstico previo a la implementación

La viabilidad técnica es real pero condicionada. Windows proporciona Virtual
HID Framework (VHF) para que un driver fuente de modo kernel enumere un HID
virtual. Esto exige KMDF/WDK, un INF correcto y una firma aceptada por Windows.
El resultado no puede considerarse seguro o distribuible por el solo hecho de
compilar.

Los bloqueos del entorno de desarrollo usado fueron:

- no es Windows y no tiene WDK, MSBuild, InfVerif, Inf2Cat o SignTool;
- no hay cuenta ni paquete de firma de producción verificable;
- no se puede ejecutar Driver Verifier, HLK, HVCI ni enumeración PnP;
- no hay autorización para instalar drivers o cambiar protecciones del sistema.

Por eso el alcance correcto de Alpha 2 fue código fuente revisable, contrato
binario, cliente fuente, diagnóstico y pruebas portables. El backend Python
nativo permanece sellado.

## Riesgos principales identificados

- Un error de memoria, concurrencia o ciclo de vida operaría en kernel.
- Un cliente que muere puede dejar botones retenidos si no existe neutralización.
- Una interfaz escribible por usuarios no privilegiados ampliaría la superficie
  de ataque.
- Un INF, filtro VHF o paquete firmado incorrectos pueden impedir el arranque del
  dispositivo o ser rechazados por Windows.
- Un HID genérico no equivale al protocolo DualSense y puede no ser reconocido
  como se espera por juegos, GameInput, Steam Input o anti-cheat.
- Usar VID/PID de terceros sería una identidad engañosa.

## Plan ejecutado

1. Preservar y verificar las bases estable y Alpha 1.
2. Basar el diseño únicamente en documentación oficial de Microsoft.
3. Definir un reporte HID genérico mínimo y mantenerlo idéntico al simulador.
4. Crear un contrato IOCTL versionado, de tamaño fijo y con secuencia creciente.
5. Implementar fuente KMDF/VHF con un único escritor, ACL restrictiva y estado
   neutral por defecto.
6. Neutralizar al cerrar el cliente, cambiar de energía o vencer un watchdog de
   500 ms.
7. Incluir cliente y proyectos fuente, sin `.sys`, CAT, certificados o comandos
   de instalación.
8. Mantener bloqueado `NativeHidBackend` hasta completar compilación, firma y
   validación Windows separadas.
9. Añadir regresiones, auditoría de privacidad, manifiesto y documentación exacta.

## Hallazgos corregidos durante la revisión

- El GUID compartido inicial usaba una macro incompatible con el conteo de
  argumentos de `DEFINE_GUID`; se reemplazó por componentes explícitos.
- Un timer periódico habría sido incompatible con ejecución pasiva KMDF. Se
  cambió por un timer pasivo de un solo disparo, rearmado únicamente al recibir
  una entrada no neutral.
- El diagnóstico comprobaba un nombre de servicio distinto al declarado en el
  INF; ambos ahora usan `NikaidoVirtualHid`.
- El chequeo de herramientas confundía SDK presente con VHF utilizable; ahora
  exige detectar `vhf.h` y `VhfKm.lib` y separa dependencia faltante de fallo de
  compilación.
- Se añadieron conversiones de tamaños explícitas para que advertencias de
  MSVC, tratadas como errores, no oculten el diagnóstico real.

Estos cambios están cubiertos estáticamente, pero no sustituyen una compilación
con WDK ni una prueba real del driver.

## Fuentes primarias

- [Virtual HID Framework](https://learn.microsoft.com/windows-hardware/drivers/hid/virtual-hid-framework--vhf-)
- [VhfCreate](https://learn.microsoft.com/windows-hardware/drivers/ddi/vhf/nf-vhf-vhfcreate)
- [VhfStart](https://learn.microsoft.com/windows-hardware/drivers/ddi/vhf/nf-vhf-vhfstart)
- [Timers de WDF](https://learn.microsoft.com/windows-hardware/drivers/wdf/using-timers)
- [INF AddReg](https://learn.microsoft.com/windows-hardware/drivers/install/inf-addreg-directive)
- [Requisitos de firma](https://learn.microsoft.com/windows-hardware/drivers/dashboard/code-signing-reqs)

© Team Nikaido
