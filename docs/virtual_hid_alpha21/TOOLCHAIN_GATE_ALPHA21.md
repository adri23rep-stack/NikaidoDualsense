# Compuerta VS2026/WDK — Alpha 2.1

## Requisitos comprobados

`CHECK_VHF_ALPHA21_ENVIRONMENT.bat` ejecuta una comprobación de solo lectura.
No descarga, instala ni configura componentes.

| Comprobación | Requisito | Salida al fallar |
| --- | --- | ---: |
| Python | 3.10 o superior | 19 |
| MSBuild | Disponible en la consola | 20 |
| Visual Studio | MSBuild 18 / Visual Studio 2026 | 21 |
| C++ | `v145`, MSVC 14.5x y `cl.exe` x64 | 22 |
| Integración WDK | `WindowsKernelModeDriver10.0/Toolset.props` | 23 |
| SDK/WDK | Mismo directorio de build 28000 con headers, libs y props | 24 |
| Spectre | Bibliotecas x64 para el MSVC activo | 25 |

El conjunto SDK/WDK debe contener, bajo una misma versión, `ntddk.h`, `vhf.h`,
`VhfKm.lib`, `Windows.h`, `SetupAPI.lib` y los props de driver de kernel. El
informe muestra versiones, pero nunca publica rutas, usuario o nombre del equipo.

## Comandos

Desde **Developer Command Prompt for VS 2026**:

```bat
CHECK_VHF_ALPHA21_ENVIRONMENT.bat
BUILD_VHF_ALPHA21.bat
```

El segundo comando vuelve a ejecutar el gate. Si pasa, compila primero el
driver y después el cliente. Un fallo posterior se clasifica como proyecto del
driver (salida 30) o proyecto cliente (salida 31). No se invoca el instalador,
Inf2Cat, firma, carga del servicio ni el cliente compilado.

## Si falta la integración WDK

En Visual Studio Installer, modifica Visual Studio 2026 y confirma:

- workload **Desktop development with C++**;
- componente individual **Windows Driver Kit**;
- SDK y WDK de la familia 28000 con el mismo número de build;
- **C++ Spectre-mitigated libraries for x64/x86 (Latest MSVC)**.

No habilites test signing ni desactives Secure Boot o Integridad de memoria.
Esas opciones no corrigen una integración de compilación incompleta.

## Referencias oficiales consultadas

- [Descarga e instalación del WDK](https://learn.microsoft.com/en-us/windows-hardware/drivers/download-the-wdk)
- [Versiones compatibles de WDK](https://learn.microsoft.com/en-us/windows-hardware/drivers/other-wdk-downloads)
- [WDK mediante NuGet](https://learn.microsoft.com/en-us/windows-hardware/drivers/install-the-wdk-using-nuget)

La variante NuGet es una opción oficial, pero Alpha 2.1 no la agrega ni la
restaura automáticamente. El gate usa la instalación local ya autorizada por el
usuario.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
