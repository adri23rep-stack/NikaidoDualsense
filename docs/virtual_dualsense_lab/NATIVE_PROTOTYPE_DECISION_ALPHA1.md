# Decisión del prototipo HID nativo — Alpha 1

## Veredicto

**Diferido por seguridad y falta de entorno verificable.**

Alpha 1 no incluye un driver instalable. La decisión no cuestiona la viabilidad
técnica: evita publicar código de kernel sin poder compilarlo, firmarlo, cargarlo
con las protecciones normales ni comprobar su reversión en Windows.

## Viabilidad real

Microsoft documenta Virtual HID Framework como mecanismo para que un driver
fuente HID KMDF/WDM cree un árbol HID virtual. La documentación actual indica
que el driver fuente VHF se ejecuta en modo kernel y enlaza `Vhfkm.lib` del WDK.

Para emular un dispositivo USB completo, Microsoft ofrece USB Device Emulation
(UDE/UdeCx), que combina un controlador host emulado y el dispositivo virtual en
un driver KMDF. Es más potente, pero aumenta superficie y riesgo.

La emulación estable de Nikaido usa `vgamepad/ViGEm` únicamente para Xbox 360 y
DualShock 4. El proyecto oficial ViGEmBus está retirado y no ofrece DualSense;
por eso no se reemplaza ni se amplía de forma improvisada.

## Por qué un gamepad HID genérico no equivale a DualSense

Botones, D-pad, sticks y gatillos pueden describirse con usos HID estándar. Ser
reconocido específicamente como DualSense también exige identidad coherente y
el comportamiento correcto de reportes de entrada, salida y funciones. Alpha 1
no suplanta VID/PID ni afirma compatibilidad con un protocolo que no verificó.

## Firma y protecciones

Windows moderno exige firma aceptada para drivers nuevos en modo kernel. Las
pruebas locales con test signing cambian el entorno de arranque y pueden entrar
en conflicto con Secure Boot; HVCI tampoco admite binarios sin firma. Este
laboratorio prohíbe esas rutas.

Un prototipo nativo futuro solo podrá habilitarse cuando:

- compile sin advertencias con WDK compatible;
- tenga análisis estático y revisión de memoria/concurrencia;
- permanezca compatible con Integridad de memoria/HVCI;
- se pruebe con Secure Boot activo;
- use firma de preproducción o producción aceptada por Microsoft;
- pase instalación, actualización, desinstalación y reversión en una máquina de prueba;
- neutralice el dispositivo ante cierre, crash, timeout o desconexión del cliente;
- no use identidad de terceros sin autorización y revisión correspondiente.

## Fuentes primarias consultadas

- Microsoft: [Virtual HID Framework](https://learn.microsoft.com/windows-hardware/drivers/hid/virtual-hid-framework--vhf-)
- Microsoft: [muestra oficial vhidmini2](https://github.com/microsoft/Windows-driver-samples/tree/main/hid/vhidmini2)
- Microsoft: [arquitectura UDE](https://learn.microsoft.com/windows-hardware/drivers/usbcon/usb-emulated-device--ude--architecture)
- Microsoft: [política de firma de drivers](https://learn.microsoft.com/windows-hardware/drivers/install/kernel-mode-code-signing-policy--windows-vista-and-later-)
- Microsoft: [requisitos actuales de firma](https://learn.microsoft.com/windows-hardware/drivers/dashboard/code-signing-reqs)
- Microsoft: [opción de arranque TESTSIGNING](https://learn.microsoft.com/windows-hardware/drivers/install/the-testsigning-boot-configuration-option)
- Microsoft: [Integridad de memoria y VBS](https://learn.microsoft.com/windows-hardware/drivers/bringup/device-guard-and-credential-guard)
- Microsoft: [NtQuerySystemInformation y Code Integrity](https://learn.microsoft.com/windows/win32/api/winternl/nf-winternl-ntquerysysteminformation)
- Nefarius: [ViGEmBus retirado](https://github.com/nefarius/ViGEmBus)
