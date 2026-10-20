# Preparación de paquete — Alpha 2.2

## Objetivo verificable

Alpha 2.2 no intenta instalar el driver. Su única meta nativa es transformar
una compilación Release x64 ya existente en una carpeta que pueda ser revisada
antes de una futura firma:

```text
NikaidoVhfA22/
  NikaidoVirtualHid.inf
  NikaidoVirtualHid.sys
  NikaidoVirtualHid.cat
```

El catálogo es generado por `Inf2Cat` y permanece sin firma.

## Fundamento técnico

- Microsoft define `InfVerif` como el validador que usa el mismo parser de INF
  que Windows y exige `InfVerif /u` para un driver Universal:
  <https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/infverif>
- Microsoft documenta que `Inf2Cat` comprueba si el paquete puede firmarse y,
  si lo aprueba, genera un catálogo todavía sin firma:
  <https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/inf2cat>
- VHF requiere un driver fuente de modo kernel y que `Vhf.sys` se declare como
  filtro inferior en el INF:
  <https://learn.microsoft.com/en-us/windows-hardware/drivers/hid/virtual-hid-framework--vhf->
- Un catálogo correcto no sustituye la firma aceptada por Windows:
  <https://learn.microsoft.com/en-us/windows-hardware/drivers/dashboard/driver-signing-offerings>

## Flujo

1. `CHECK_VHF_ALPHA22_ENVIRONMENT.bat` valida por separado el toolchain de
   compilación, `InfVerif.exe` e `Inf2Cat.exe`.
2. `BUILD_VHF_ALPHA22.bat` reconstruye el driver y el cliente con advertencias
   tratadas como errores.
3. `PREPARE_VHF_ALPHA22_PACKAGE.bat` exige que el `.sys` sea posterior a todas
   sus fuentes relevantes.
4. El preparador comprueba la cabecera PE sin cargar el archivo:
   - arquitectura AMD64;
   - formato PE32+;
   - marca de binario de sistema;
   - subsistema Native;
   - tabla de certificados vacía.
5. Copia el INF fuente con `DriverVer=07/21/2026,3.0.0.220` y el `.sys` a un
   directorio temporal controlado.
6. Bloquea rutas de INF mayores de 259 caracteres.
7. Ejecuta `InfVerif /v /u`.
8. Ejecuta `Inf2Cat /uselocaltime /verbose` para:
   - `10_VB_X64`;
   - `10_CO_X64`;
   - `10_NI_X64`;
   - `10_GE_X64`;
   - `10_25H2_X64`.
9. Comprueba que el catálogo exista y no esté vacío.
10. Publica la carpeta final y un manifiesto adyacente con SHA-256.

La fecha del INF usa el 21 de julio para evitar un falso “DriverVer futuro” en
equipos cuya zona horaria todavía no haya cambiado al día 22. La versión del
driver sigue siendo exclusiva de Alpha 2.2.

## Resolución de herramientas

El comprobador prueba primero las ubicaciones x64 del kit seleccionado y solo
usa x86 como fallback. `InfVerif` y `Inf2Cat` deben pertenecer a la misma raíz
SDK/WDK; nunca se combinan herramientas de instalaciones distintas. Los
informes JSON exponen únicamente etiquetas relativas como `Tools/x64` o
`bin/<kit>/x64`.

## Códigos de salida del preparador

| Código | Significado |
|---:|---|
| 40 | Toolchain SDK/WDK no listo |
| 41 | `InfVerif.exe` ausente |
| 42 | `Inf2Cat.exe` ausente |
| 43 | `.sys` compilado ausente |
| 44 | Artefacto o identidad local inválida |
| 45 | Ruta incompatible con el límite de `InfVerif` |
| 46 | `InfVerif /u` rechazó el INF |
| 47 | `Inf2Cat` rechazó el paquete |
| 48 | Catálogo esperado ausente o vacío |
| 49 | Fallo de E/S en la salida controlada |

## Privacidad y limpieza

La salida capturada de WDK reemplaza la carpeta del proyecto, el perfil de
usuario, el nombre de usuario y el hostname antes de mostrarla. El manifiesto
no incluye rutas absolutas, fechas de ejecución ni identificadores de equipo.

Una validación fallida elimina únicamente el directorio temporal fijo dentro de
`native\\vhf\\out`. Se rechazan enlaces simbólicos y cualquier destino fuera de
esa raíz. Nunca se eliminan fuentes o carpetas elegidas por el usuario.

## Límite

No se llama a `SignTool`, `PnPUtil`, DevCon, SetupAPI de instalación, creación
de servicios ni configuración de arranque. Incluso un resultado aprobado por
`InfVerif` e `Inf2Cat` continúa bloqueado hasta obtener una firma aceptada y
realizar pruebas separadas en Windows.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
