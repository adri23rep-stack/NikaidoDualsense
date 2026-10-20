# Diagnóstico y plan — Nikaido DualSense 3.0.0 Alpha 2.3.0

## Aislamiento y procedencia

Alpha 2.3.0 parte de una copia completa e independiente de Alpha 2.2.3. La
base Alpha 2.2.3 permanece sin modificaciones y su ZIP tiene SHA-256:

`7ba0ff887ac071f4075f35c0043568717821e44c9e2e74827685fcceee95275c`

El manifiesto de Alpha 2.2.3 contiene 535 entradas válidas. El árbol base
contiene 536 archivos porque el manifiesto no se incluye a sí mismo. No se
detectaron archivos ausentes, alterados o inesperados.

La base estable 2.9.8.9 continúa inmutable con SHA-256:

`14ea6788a36b620ec907a508c67e307aad8ccbec5a6235ba199e5e5910a29338`

El laboratorio no reutiliza configuraciones, perfiles, runtime, emulación ni
interfaz de la versión estable.

## Evidencia disponible antes de escribir código

La ejecución comunicada desde Windows para Alpha 2.2.3 confirmó:

- Driver KMDF/VHF y cliente x64 compilados con 0 advertencias y 0 errores.
- Registro de compilación por hashes creado correctamente.
- `InfVerif /u` aprobó el INF Universal.
- `Inf2Cat` terminó sin errores ni advertencias.
- Se generó un catálogo local sin firma.
- No se firmó, instaló ni cargó el driver.

Hashes comunicados del paquete sin firma:

| Archivo | SHA-256 |
|---|---|
| `NikaidoVirtualHid.inf` | `a8aa65ac61c6e1990bdce7dea83dfc3fa178b980e89347798c0b37e6758989e6` |
| `NikaidoVirtualHid.sys` | `e66ce955382f05c1f12c4c0494821f6afa18ddcac2241f60753a2611ec35ae07` |
| `NikaidoVirtualHid.cat` | `9c6be45193c9bb93b1b0f7e06ad6b0c1d768d03d0743665f6b39996f1ab9d0f8` |

Esta evidencia demuestra que la cadena de compilación y validación del paquete
funciona en ese entorno. No demuestra firma aceptada, instalación, carga,
enumeración HID, estabilidad en kernel ni compatibilidad con juegos.

## Causa del bloqueo actual

El catálogo producido por `Inf2Cat` acredita la composición del paquete, pero
permanece sin una firma confiable para el kernel. Windows no debe cargar este
driver en un sistema de producción hasta que Microsoft lo firme mediante un
flujo admitido.

Según la documentación oficial de Microsoft consultada el 23 de julio de 2026:

- Los nuevos drivers kernel de Windows 10 versión 1607 y posteriores deben
  recibir firma mediante el portal de hardware.
- La atestación sirve para escenarios de prueba, no equivale a certificación
  de compatibilidad y no permite publicación retail en Windows Update.
- La cuenta de Hardware Dev Center debe tener asociado un certificado EV
  vigente.
- El CAB de presentación debe contener cada paquete dentro de una subcarpeta;
  normalmente incluye INF, SYS, PDB y CAT.
- Microsoft reemplaza el CAT presentado y agrega la firma correspondiente al
  binario cuando procesa una presentación aprobada.
- El cross-signing ya no es una alternativa admitida para nuevos drivers.

Referencias oficiales:

- https://learn.microsoft.com/windows-hardware/drivers/dashboard/code-signing-attestation
- https://learn.microsoft.com/windows-hardware/drivers/dashboard/driver-signing-offerings
- https://learn.microsoft.com/windows-hardware/drivers/dashboard/code-signing-reqs
- https://learn.microsoft.com/windows-hardware/drivers/install/kernel-mode-code-signing-policy--windows-vista-and-later-
- https://learn.microsoft.com/windows-hardware/drivers/install/deprecation-of-software-publisher-certificates-and-commercial-release-certificates
- https://learn.microsoft.com/windows-hardware/drivers/devtest/signtool

## Riesgos identificados

1. Un driver firmado aún puede contener errores capaces de afectar la
   estabilidad del sistema.
2. Un certificado o clave privada nunca debe incluirse en el proyecto ni ser
   manipulado automáticamente por el laboratorio.
3. Un PDB puede contener rutas del equipo de compilación. La preparación debe
   bloquearse si detecta una ruta de perfil de usuario.
4. La firma modifica el SYS y reemplaza el CAT. Los hashes simples no bastan
   para demostrar que el código del SYS devuelto sigue siendo el mismo.
5. Un CAB con archivos en la raíz, nombres especiales o carpetas largas puede
   ser rechazado por Partner Center.
6. Una firma válida no demuestra enumeración VHF, descriptor HID correcto,
   estabilidad con HVCI, suspensión/reanudación o compatibilidad con juegos.
7. Instalar antes de validar firma, procedencia e identidad ampliaría
   innecesariamente el riesgo.

## Plan de Alpha 2.3.0

1. Conservar sin cambios `driver.c`, el protocolo VHF y el backend nativo
   sellado.
2. Actualizar únicamente la identidad de la copia Alpha 2.3.0 y sus wrappers.
3. Extender el registro de compilación para incluir el PDB requerido y sus
   hashes, sin rutas absolutas.
4. Mantener `InfVerif` e `Inf2Cat` como etapas previas obligatorias.
5. Añadir una comprobación de herramientas de firma que no consulte el almacén
   de certificados ni solicite elevación.
6. Crear un CAB sin firma con una subcarpeta corta y alfanumérica, usando un DDF
   temporal que se elimina al finalizar.
7. Bloquear la creación del CAB si faltan hashes, el PDB no coincide o aparece
   una ruta privada conocida.
8. Añadir un verificador de solo lectura para un directorio devuelto por
   Microsoft. Debe usar `SignTool verify /kp`, comprobar pertenencia al CAT y
   comparar una huella normalizada del contenido PE sin contar la firma.
9. Añadir pruebas de regresión portables para estructura, privacidad,
   trazabilidad, normalización PE y ausencia de acciones peligrosas.
10. Mantener bloqueadas firma automática, presentación, instalación, carga,
    creación del dispositivo raíz y enumeración.

## Criterio de salida

Alpha 2.3.0 termina cuando puede preparar de forma reproducible un CAB sin
firma, explicar qué falta para presentarlo y verificar criptográficamente una
respuesta de Microsoft sin instalarla. La enumeración HID queda para una fase
posterior y solo después de recibir y validar una firma aceptada.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
