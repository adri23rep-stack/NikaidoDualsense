# Preparación para firma de Microsoft — Alpha 2.3.0

## Alcance

Alpha 2.3.0 añade una etapa aislada entre el paquete local sin firma y una
posible presentación externa a Microsoft. No firma, envía, instala ni carga el
driver. Tampoco consulta certificados, solicita elevación o cambia la
configuración de Windows.

La arquitectura queda dividida en cinco etapas:

| Etapa | Entrada | Salida | Cambios en Windows |
|---|---|---|---|
| Compilación | Fuentes KMDF/VHF | SYS, PDB y cliente locales | Ninguno |
| Paquete | Registro por hashes | INF, SYS, CAT sin firma y manifiesto | Ninguno |
| Presentación | Paquete validado y PDB | CAB sin firma y manifiesto | Ninguno |
| Firma externa | CAB firmado por el titular | Respuesta procesada por Microsoft | Fuera del laboratorio |
| Verificación | Carpeta extraída devuelta | Informe en memoria | Ninguno |

Cada etapa rechaza una entrada que no conserve los hashes de la etapa anterior.
Compilar no autoriza el paquete; crear el CAT no autoriza la instalación; crear
el CAB no autoriza la presentación; recibir una firma no instala el driver.

## Contenido del CAB

`CREATE_VHF_ALPHA230_SUBMISSION_CAB.bat` exige este contenido exacto:

```text
NikaidoVhfA230\
  NikaidoVirtualHid.inf
  NikaidoVirtualHid.sys
  NikaidoVirtualHid.pdb
  NikaidoVirtualHid.cat
```

La subcarpeta es alfanumérica y tiene menos de 40 caracteres. El DDF utilizado
por MakeCab contiene necesariamente rutas locales, por lo que es temporal y se
elimina antes de publicar la salida. El manifiesto final solo conserva rutas
relativas, tamaños y SHA-256.

El creador comprueba:

- manifiesto del paquete, versión y publisher;
- hashes de INF, SYS, CAT y PDB;
- aprobación previa de InfVerif e Inf2Cat;
- ausencia de firma en el paquete local;
- ausencia de marcadores privados conocidos;
- cabecera `MSCF`;
- tabla de archivos del CAB;
- ausencia de archivos en la raíz;
- ausencia de entradas duplicadas o inesperadas.

El CAB termina deliberadamente sin firma. El laboratorio no incluye una orden
de firma porque el certificado EV y su clave deben permanecer bajo custodia del
titular autorizado.

## Flujo local

En Developer Command Prompt for VS 2026:

```console
cd /d C:\Nikaido230
CHECK_VHF_ALPHA230_SIGNING_READINESS.bat
BUILD_VHF_ALPHA230.bat
PREPARE_VHF_ALPHA230_PACKAGE.bat
CREATE_VHF_ALPHA230_SUBMISSION_CAB.bat
```

Salidas locales esperadas:

```text
native\vhf\out\NikaidoVhfA230\
native\vhf\out\NikaidoVhfA230.manifest.json
native\vhf\out\NikaidoVhfA230Submission.cab
native\vhf\out\NikaidoVhfA230Submission.manifest.json
```

Estas salidas se generan en la copia local y no forman parte del ZIP fuente.

## Paso externo

Antes de cualquier presentación hacen falta una organización inscrita en
Windows Hardware Developer Program, una cuenta de Hardware Dev Center con un
certificado EV vigente asociado y un procedimiento de firma autorizado por el
proveedor del certificado.

La vía de atestación documentada por Microsoft es adecuada para pruebas, pero
no concede la denominación Windows Certified ni distribución retail mediante
Windows Update. La ruta de producción requiere el proceso de certificación
aplicable, incluidas las pruebas HLK cuando correspondan.

Alpha 2.3.0 no automatiza la autenticación, firma, carga a Partner Center ni
descarga de la respuesta.

## Verificación de la respuesta

Después de descargar y extraer el resultado procesado por Microsoft:

```console
VERIFY_VHF_ALPHA230_MICROSOFT_RETURN.bat "C:\Ruta\PaqueteExtraido"
```

La carpeta debe contener INF, SYS y CAT directamente en su raíz. El PDB es
opcional. El verificador:

1. vuelve a validar el paquete local y los hashes del CAB presentado;
2. exige que el INF devuelto sea idéntico al presentado;
3. exige una firma PE incrustada en el SYS devuelto;
4. compara cabeceras y secciones del SYS, normalizando únicamente el checksum
   y el directorio de certificados;
5. si existe PDB devuelto, exige que sea idéntico al presentado;
6. ejecuta `SignTool verify /kp /v /all` sobre CAT y SYS;
7. ejecuta `SignTool verify /kp /v /c` para comprobar la pertenencia de INF y
   SYS al catálogo.

No se copia ni instala el resultado. Una aprobación solo acredita firma,
pertenencia y continuidad del contenido presentado; no acredita enumeración,
estabilidad del kernel ni compatibilidad con juegos.

## Riesgos que siguen abiertos

- defectos de memoria, sincronización o ciclo de vida dentro del driver;
- diferencias entre versiones de Windows, VHF, KMDF y HVCI;
- instalación, actualización, recuperación y desinstalación;
- suspensión, reanudación y desconexión inesperada;
- Driver Verifier y pruebas HLK;
- enumeración HID real y recepción de reportes por el sistema;
- interpretación del descriptor por juegos y software de entrada;
- requisitos de distribución y mantenimiento de una firma de producción.

## Referencias oficiales

Consultadas el 23 de julio de 2026:

- https://learn.microsoft.com/windows-hardware/drivers/dashboard/code-signing-attestation
- https://learn.microsoft.com/windows-hardware/drivers/dashboard/driver-signing-offerings
- https://learn.microsoft.com/windows-hardware/drivers/dashboard/code-signing-reqs
- https://learn.microsoft.com/windows-hardware/drivers/install/kernel-mode-code-signing-policy--windows-vista-and-later-
- https://learn.microsoft.com/windows-hardware/drivers/install/deprecation-of-software-publisher-certificates-and-commercial-release-certificates
- https://learn.microsoft.com/windows-hardware/drivers/devtest/signtool
- https://learn.microsoft.com/cpp/build/reference/pdbaltpath-use-alternate-pdb-path

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
