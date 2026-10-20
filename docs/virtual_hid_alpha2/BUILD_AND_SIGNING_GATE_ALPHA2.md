# Puerta de compilación y firma — Alpha 2

## Estado

El paquete contiene código fuente, no un driver instalable. `SignMode` está en
`Off` e Inf2Cat automático está desactivado para que una compilación local no se
confunda con un paquete apto para distribución.

## Herramientas requeridas

- Windows 11 x64 de desarrollo.
- Visual Studio 2022 con Desktop development with C++.
- Windows Driver Kit compatible con la versión de Visual Studio.
- Windows SDK y MSBuild desde Developer Command Prompt.

`CHECK_VHF_ALPHA2_ENVIRONMENT.bat` solo informa si MSBuild y WDK parecen estar
disponibles. `BUILD_VHF_ALPHA2.bat` únicamente llama MSBuild; no instala, carga
o firma el resultado.

## Por qué el resultado compilado sigue bloqueado

Un `.sys` nuevo debe recibir una firma aceptada por Windows. La documentación
actual de Microsoft exige una cuenta del Hardware Dev Center vinculada con un
certificado EV para enviar un paquete a firma de atestación o certificación.
Alpha 2 no posee ni simula esa identidad.

No se ofrece el camino de test signing porque cambiaría la política de arranque
y no sería una prueba representativa de distribución. Tampoco se pide desactivar
Secure Boot o Integridad de memoria.

## Criterios para desbloquear una fase nativa

Todos deben cumplirse:

1. Compilación Release x64 con WDK y cero advertencias.
2. `InfVerif` e `Inf2Cat` aprobados sobre un paquete separado.
3. Code Analysis for Drivers y revisión manual de concurrencia/memoria.
4. Compatibilidad HVCI comprobada con Integridad de memoria habilitada.
5. Paquete firmado y verificable mediante `signtool verify /kp`.
6. Instalación y eliminación probadas en una máquina Windows de laboratorio.
7. Driver Verifier sin fallos en ciclos de abrir, cerrar, suspender y reanudar.
8. Enumeración comprobada con Administrador de dispositivos y herramientas HID.
9. Neutralización confirmada tras matar el cliente y esperar el watchdog.
10. Revisión de identidad antes de usar un VID/PID distinto de cero.

Hasta entonces, `NativeHidBackend` permanecerá sellado.

## Fuentes primarias

- [Requisitos de firma de drivers](https://learn.microsoft.com/windows-hardware/drivers/dashboard/code-signing-reqs)
- [Opciones de firma](https://learn.microsoft.com/windows-hardware/drivers/dashboard/driver-signing-offerings)
- [Compatibilidad con Integridad de memoria](https://learn.microsoft.com/windows-hardware/drivers/bringup/device-guard-and-credential-guard)
- [Prueba manual de paquetes](https://learn.microsoft.com/windows-hardware/drivers/develop/test-a-driver-package-manual-deployment)

© Team Nikaido

