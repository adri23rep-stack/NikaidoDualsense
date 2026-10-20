# Compuerta VS2026/WDK — Alpha 2.1.4

## Diagnóstico de solo lectura

Desde Developer Command Prompt for VS 2026, en la raíz del proyecto:

```bat
CHECK_VHF_ALPHA214_ENVIRONMENT.bat
```

La compuerta comprueba MSBuild 18, `v145`, integración
`WindowsKernelModeDriver10.0`, SDK/WDK 28000 emparejados, componentes VHF,
tareas de build WDK y bibliotecas Spectre x64. No instala ni repara nada.

`Inf2Cat.exe` no es un requisito de esta Alpha porque la etapa de catálogo está
desactivada expresamente. Será obligatorio en una fase futura que valide un
paquete INF destinado a catálogo y firma.

## Compilación fuente

```bat
BUILD_VHF_ALPHA214.bat
```

El script ejecuta primero la compuerta, después compila por separado:

1. driver KMDF/VHF Release x64;
2. cliente diagnóstico Release x64.

El proyecto del driver contiene exactamente:

```xml
<SignMode>Off</SignMode>
<EnableInf2cat>false</EnableInf2cat>
```

No debe contener `RunInf2Cat`. Para comprobar la copia extraída:

```bat
findstr /i "EnableInf2cat RunInf2Cat SignMode" native\vhf\driver\NikaidoVirtualHid.vcxproj
```

## Interpretación

- `ClCompile`, `Link` y `ApiValidator` correctos prueban compilación y
  validación estática del binario, no enumeración HID.
- La omisión de `Inf2Cat` significa que no se valida ni genera el catálogo.
- Un `.sys` local sin catálogo ni firma no es un paquete instalable.
- El cliente solo podrá abrir la interfaz después de una futura instalación
  segura y validada; Alpha 2.1.4 no realiza esa operación.

## Seguridad

No uses el `.sys` parcial generado por una compilación anterior. No habilites
test signing ni desactives Secure Boot o Integridad de memoria. Este laboratorio
no requiere esos cambios y no contiene comandos para realizarlos.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
