# Preparación de paquete — Alpha 2.2.1

## Objetivo verificable

Alpha 2.2.1 corrige la detección de la herramienta de catálogo sin cambiar el
driver, el protocolo HID ni la política de seguridad. La salida esperada es:

```text
NikaidoVhfA221/
  NikaidoVirtualHid.inf
  NikaidoVirtualHid.sys
  NikaidoVirtualHid.cat
```

El CAT permanece sin firma y no está autorizado para instalarse.

## Separación de kits

| Componente | Selección |
|---|---|
| Headers, bibliotecas, VHF y tareas WDK | Kit de compilación 28000 |
| MSBuild y MSVC | Toolchain validado por el preflight |
| `InfVerif` | Preferentemente el kit 28000 |
| `Inf2Cat` | Kit 28000; si falta, candidato desde 26100 en la misma raíz |

No se copian headers ni herramientas entre kits. La ruta absoluta nunca se
incluye en los informes o manifiestos.

## Flujo

1. `CHECK_VHF_ALPHA221_ENVIRONMENT.bat` comprueba el toolchain y las
   herramientas de paquete.
2. `BUILD_VHF_ALPHA221.bat` reconstruye driver y cliente con
   `EnableInf2cat=false` y `SignMode=Off`.
3. `PREPARE_VHF_ALPHA221_PACKAGE.bat` valida que el SYS sea reciente, Native
   x64, binario de sistema y sin firma incrustada.
4. `InfVerif /v /u` valida el INF Universal.
5. `Inf2Cat` recibe sin reducciones:
   - `10_VB_X64`;
   - `10_CO_X64`;
   - `10_NI_X64`;
   - `10_GE_X64`;
   - `10_25H2_X64`.
6. Solo un código cero y un CAT no vacío publican la carpeta final.
7. El manifiesto registra hashes, kit de compilación, kit de cada herramienta,
   arquitectura y ausencia de acciones del sistema.

## Disposición Windows observada

La evidencia comunicada corresponde a:

- compilación e `InfVerif`: `10.0.28000.0`, x64;
- candidato `Inf2Cat`: `10.0.26100.0`, x86.

Esta disposición está cubierta por regresión portable. Su aceptación real de
los destinos solo puede verificarse al ejecutar el preparador en Windows.

## Códigos de salida

| Código | Significado |
|---:|---|
| 40 | Toolchain SDK/WDK no listo |
| 41 | `InfVerif.exe` ausente |
| 42 | `Inf2Cat.exe` no localizado en una ubicación compatible |
| 43 | SYS compilado ausente |
| 44 | Artefacto o identidad local inválida |
| 45 | Ruta incompatible con el límite de `InfVerif` |
| 46 | `InfVerif /u` rechazó el INF |
| 47 | `Inf2Cat` rechazó el paquete o los destinos |
| 48 | CAT esperado ausente o vacío |
| 49 | Fallo de E/S en la salida controlada |

## Límite de seguridad

No se llama a `SignTool`, PnPUtil, DevCon, SetupAPI de instalación, creación de
servicios ni configuración de arranque. Los scripts no solicitan elevación
automática ni cambian Secure Boot, Integridad de memoria o test signing.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
