# Compuerta VS2026/WDK — Alpha 2.1.3

## Comando de diagnóstico

```bat
CHECK_VHF_ALPHA213_ENVIRONMENT.bat
```

La compuerta es de solo lectura. Comprueba MSBuild 18, Visual Studio 2026,
MSVC 14.5x/v145, integración `WindowsKernelModeDriver10.0`, Spectre x64 y un
kit 28000 autocontenido.

El kit seleccionado debe contener:

- `ntddk.h`;
- `shared\vhf.h`;
- `guiddef.h`;
- `Windows.h`;
- `VhfKm.lib`;
- `SetupAPI.lib`;
- `WindowsDriver.KernelMode.Driver.props`;
- `Microsoft.DriverKit.Build.Tasks.18.0.dll`.

No se combinan componentes de dos raíces ni de dos versiones de kit.

## Comando de compilación

```bat
BUILD_VHF_ALPHA213.bat
```

El comando ejecuta primero la compuerta y después compila por separado el
driver y el cliente. No firma, instala, carga ni registra servicios. Un resultado
correcto solo demuestra compilación local.

## Corrección C4117

`NikaidoVirtualHid.vcxproj` no define `_KERNEL_MODE`. La macro pertenece al
toolset de kernel. El proyecto conserva advertencias de nivel 4 tratadas como
errores; no usa `/wd4117` ni deshabilita `/WX`.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
