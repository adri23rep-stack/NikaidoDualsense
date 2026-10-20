# Compuerta VS2026/WDK — Alpha 2.1.1

> **Documento histórico sustituido:** `vhf.h` pertenece a
> `Include\<versión>\shared`. No repares ni reinstales el WDK basándote en el
> bloqueo de Alpha 2.1.1; utiliza el comprobador corregido de Alpha 2.1.2.

## Uso

Desde **Developer Command Prompt for VS 2026**:

```bat
CHECK_VHF_ALPHA211_ENVIRONMENT.bat
```

El informe mostrará por separado:

- `ntddk.h`;
- `vhf.h`;
- `guiddef.h`;
- `Windows.h`;
- `VhfKm.lib`;
- `SetupAPI.lib`;
- `WindowsDriver.KernelMode.Driver.props`.

Solo si todos aparecen como `OK` se puede ejecutar:

```bat
BUILD_VHF_ALPHA211.bat
```

## Si únicamente falta `vhf.h`

No repitas la reparación de Visual Studio y no copies el archivo desde el kit
26100. La integración de Visual Studio ya está confirmada por separado. Revisa
el **Windows Driver Kit independiente** y su correspondencia con el SDK 28000.

Microsoft documenta el proceso en pasos distintos: Visual Studio y su componente
de integración, Windows SDK y Windows Driver Kit. Los enlaces de SDK y WDK
oficiales deben corresponder a la misma familia de build.

Referencias:

- [Descargar el WDK](https://learn.microsoft.com/en-us/windows-hardware/drivers/download-the-wdk)
- [Versiones compatibles del WDK](https://learn.microsoft.com/en-us/windows-hardware/drivers/other-wdk-downloads)
- [VhfCreate requiere `vhf.h` y `VhfKm.lib`](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/vhf/nf-vhf-vhfcreate)

## Seguridad

El comprobador es de solo lectura. El comando de compilación no instala, carga
ni firma el resultado. Ningún script cambia Secure Boot, HVCI, Integridad de
memoria o test signing. Una compilación correcta tampoco autoriza instalar el
`.sys` generado.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
