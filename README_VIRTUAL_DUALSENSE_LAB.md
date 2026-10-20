# Nikaido DualSense 3.0.0 Alpha 2.3.0

## Microsoft Signing Readiness

Alpha 2.3.0 es una copia independiente de Alpha 2.2.3. Prepara el prototipo
KMDF/VHF para una futura presentación de firma de Microsoft sin firmar,
instalar, cargar ni integrar el driver en la interfaz principal.

El objetivo verificable de esta versión es producir un CAB de presentación
trazable y comprobar, posteriormente, que un paquete devuelto por Microsoft
conserva el mismo contenido de driver y cumple la política de firma de kernel.
No promete todavía enumeración HID ni emulación completa de DualSense.

## Procedencia verificada

- Base estable 2.9.8.9:
  `14ea6788a36b620ec907a508c67e307aad8ccbec5a6235ba199e5e5910a29338`
- Alpha 2.2.2:
  `56cb9ad6d910d4d21e85ddf9cc07303ff01005221dce2676f966975c8ce9b937`
- Alpha 2.2.3:
  `7ba0ff887ac071f4075f35c0043568717821e44c9e2e74827685fcceee95275c`

La cadena completa desde Alpha 1 se conserva en
`VIRTUAL_DUALSENSE_LAB_PROJECT.json`.

## Evidencia real disponible

La ejecución comunicada desde Windows para Alpha 2.2.3 confirmó:

- Driver y cliente Release x64 compilados con 0 advertencias y 0 errores.
- Registro de compilación por hashes aprobado.
- `InfVerif /u`: INF Universal válido.
- `Inf2Cat`: 0 errores, 0 advertencias y CAT generado.
- El paquete quedó sin firma y no se instaló ni cargó.

Hashes del paquete Alpha 2.2.3 comunicado:

| Archivo | SHA-256 |
|---|---|
| `NikaidoVirtualHid.inf` | `a8aa65ac61c6e1990bdce7dea83dfc3fa178b980e89347798c0b37e6758989e6` |
| `NikaidoVirtualHid.sys` | `e66ce955382f05c1f12c4c0494821f6afa18ddcac2241f60753a2611ec35ae07` |
| `NikaidoVirtualHid.cat` | `9c6be45193c9bb93b1b0f7e06ad6b0c1d768d03d0743665f6b39996f1ab9d0f8` |

Alpha 2.3.0 no se compiló en Windows dentro del entorno de preparación de este
ZIP. Sus resultados de compilación, CAB y firma deben verificarse con los
comandos indicados abajo.

## Qué añade Alpha 2.3.0

- Registro por hashes del SYS, el PDB y las cuatro entradas fuente relevantes.
- `/PDBALTPATH:%_PDB%` para que el SYS no guarde la ruta local completa del PDB.
- Bloqueo si INF, SYS, CAT o PDB contienen marcadores privados conocidos del
  entorno de compilación.
- CAB con una sola subcarpeta alfanumérica menor de 40 caracteres.
- Inclusión de INF, SYS, PDB y CAT, tal como requiere el flujo de atestación.
- DDF temporal eliminado al terminar; no se publica ninguna ruta absoluta.
- Parser propio de la tabla de archivos CAB para comprobar que no existan
  archivos en la raíz ni entradas inesperadas.
- Manifiesto sanitizado del CAB y todos sus hashes.
- Detección de `SignTool` sin consultar el almacén de certificados.
- Verificación posterior con `SignTool verify /kp` para SYS, CAT y pertenencia
  de INF/SYS al catálogo.
- Comparación de cabeceras y secciones PE antes y después de firmar, excluyendo
  solamente checksum y tabla de certificados.

## Uso en Windows

Abre Developer Command Prompt for VS 2026 dentro de una ruta corta que no
contenga un nombre de usuario. Por ejemplo:

```console
cd /d C:\Nikaido230
CHECK_VHF_ALPHA230_SIGNING_READINESS.bat
BUILD_VHF_ALPHA230.bat
PREPARE_VHF_ALPHA230_PACKAGE.bat
CREATE_VHF_ALPHA230_SUBMISSION_CAB.bat
```

Los comandos deben ejecutarse en ese orden. El cuarto comando crea:

```text
native\vhf\out\NikaidoVhfA230Submission.cab
native\vhf\out\NikaidoVhfA230Submission.manifest.json
```

El CAB contiene:

```text
NikaidoVhfA230\
  NikaidoVirtualHid.inf
  NikaidoVirtualHid.sys
  NikaidoVirtualHid.pdb
  NikaidoVirtualHid.cat
```

## Firma y Partner Center

El CAB creado por el laboratorio está deliberadamente sin firma y no está
listo para enviarse todavía. Alpha 2.3.0 no accede a certificados ni claves.

El paso externo requiere:

1. Una organización registrada en Windows Hardware Developer Program.
2. Un certificado EV vigente asociado a la cuenta de Hardware Dev Center.
3. Firmar el CAB mediante el proceso indicado por el proveedor del certificado.
4. Presentar el CAB firmado en Partner Center como atestación para pruebas.
5. Descargar y extraer el paquete procesado por Microsoft.

La atestación es para escenarios de prueba. No convierte el driver en Windows
Certified y no habilita publicación retail en Windows Update. Para
certificación y distribución de producción se requiere WHCP/HLK.

Referencias oficiales consultadas el 23 de julio de 2026:

- https://learn.microsoft.com/windows-hardware/drivers/dashboard/code-signing-attestation
- https://learn.microsoft.com/windows-hardware/drivers/dashboard/driver-signing-offerings
- https://learn.microsoft.com/windows-hardware/drivers/dashboard/code-signing-reqs
- https://learn.microsoft.com/windows-hardware/drivers/install/kernel-mode-code-signing-policy--windows-vista-and-later-
- https://learn.microsoft.com/windows-hardware/drivers/devtest/signtool

## Verificar la respuesta de Microsoft

Después de descargar y extraer el paquete firmado, coloca INF, SYS y CAT juntos
en una carpeta. PDB es opcional en la respuesta. Ejecuta:

```console
VERIFY_VHF_ALPHA230_MICROSOFT_RETURN.bat "C:\Ruta\PaqueteExtraido"
```

La verificación:

- no copia el paquete;
- no instala el driver;
- no crea un dispositivo raíz;
- no solicita elevación;
- exige firma de kernel válida con `/kp`;
- exige que INF y SYS pertenezcan al CAT;
- exige que el INF sea idéntico al presentado;
- exige que las cabeceras y secciones del SYS sean idénticas salvo los campos
  propios de la firma.

Una aprobación de este comando solo habilita planear una prueba controlada de
enumeración en una versión posterior.

## Qué sigue bloqueado

- Firma automática o almacenamiento de certificados.
- Envío automático a Partner Center.
- Firma de producción WHCP/HLK.
- Instalación, actualización o eliminación del driver.
- Creación del dispositivo raíz y carga del SYS.
- Enumeración VHF y pruebas en `joy.cpl`.
- Driver Verifier, HVCI, suspensión/reanudación y recuperación ante fallo.
- Pruebas con DualSense físico, juegos o anti-cheat.
- Identidad VID/PID o protocolo propietario de terceros.
- Háptica, audio, luces, touchpad de coordenadas, movimiento y gatillos
  adaptativos virtuales.

## Seguridad y privacidad

El ZIP fuente no incluye SYS, CAT, CAB, PDB, certificados, claves ni
instaladores de driver. Los artefactos generados permanecen en la copia local y
están excluidos de la distribución. No existen comandos de instalación,
creación de servicios, `bcdedit`, test signing ni cambios de Secure Boot o
Integridad de memoria.

Los nombres de comandos anteriores se conservan como wrappers compatibles y
redirigen al flujo Alpha 2.3.0.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
