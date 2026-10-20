# Prototipo fuente KMDF/VHF — Alpha 2.3.0

Esta carpeta contiene el prototipo nativo aislado de Nikaido DualSense. El ZIP
fuente no incluye binarios generados, catálogos, PDB, CAB, certificados,
instaladores ni claves.

## Componentes

- `driver/`: fuente KMDF/VHF, INF y proyecto WDK.
- `client/`: cliente de diagnóstico de usuario.
- `shared/`: contrato IOCTL y reporte HID genérico.
- `tools/check_vs2026_wdk.py`: comprobador de toolchain de solo lectura.
- `tools/package_driver.py`: registro por hashes, InfVerif e Inf2Cat.
- `tools/signing_readiness.py`: CAB sin firma y verificación de respuesta.

`driver.c` y `shared/nikaido_vhf_protocol.h` permanecen iguales a Alpha 2.2.3.
Alpha 2.3.0 no altera el descriptor ni amplía funciones del dispositivo.

## Flujo

```console
CHECK_VHF_ALPHA230_SIGNING_READINESS.bat
BUILD_VHF_ALPHA230.bat
PREPARE_VHF_ALPHA230_PACKAGE.bat
CREATE_VHF_ALPHA230_SUBMISSION_CAB.bat
```

La compilación usa `SignMode=Off` y `EnableInf2cat=false`. Después de compilar,
el preparador ejecuta InfVerif e Inf2Cat explícitamente. El registro de build
incluye hashes relativos del SYS, PDB y fuentes; cambiar cualquiera invalida el
paquete.

El CAB contiene INF, SYS, PDB y CAT dentro de `NikaidoVhfA230`. No hay archivos
en la raíz. El DDF con rutas locales es temporal y se elimina. El manifiesto
publicado no guarda usuario, hostname ni rutas privadas.

El CAB permanece sin firma. Debe firmarse fuera del laboratorio mediante un
certificado registrado y presentarse siguiendo la documentación de Microsoft.
No se incluyen comandos de firma porque la custodia de certificados y claves
pertenece al titular.

## Respuesta firmada

`VERIFY_VHF_ALPHA230_MICROSOFT_RETURN.bat` acepta una carpeta extraída con INF,
SYS y CAT. Usa SignTool exclusivamente en modo `verify /kp`; nunca usa una
operación de firma. Compara el contenido de cabeceras y secciones del SYS con
el original y rechaza cualquier cambio distinto de checksum y certificado.

## Límites

Ningún comando de esta carpeta:

- instala o carga el driver;
- crea servicios o dispositivos raíz;
- consulta el almacén de certificados;
- solicita elevación;
- usa red o presenta archivos;
- cambia Secure Boot, HVCI o test signing.

Una firma válida no demuestra enumeración HID ni estabilidad en kernel.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
