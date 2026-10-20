# Diagnóstico y plan — Alpha 2.1.3

## Evidencia de Windows

Alpha 2.1.2 superó la compuerta de toolchain y MSBuild inició correctamente el
proyecto `NikaidoVirtualHid.vcxproj` con:

- MSBuild 18.8.2;
- PlatformToolset `WindowsKernelModeDriver10.0`;
- WDK/SDK 28000;
- KMDF 1.15;
- compilación Release x64 con `/W4` y `/WX`.

La ejecución alcanzó `ClCompile` y se detuvo con C4117/C2220. No se instaló ni
cargó ningún resultado.

## Causa

El proyecto agregaba manualmente `_KERNEL_MODE` a
`PreprocessorDefinitions`. El toolset de kernel del WDK ya administra esa macro
reservada. El compilador ignoró la redefinición, emitió C4117 y `/WX` convirtió
la advertencia en C2220.

Este fallo pertenece a la configuración del proyecto. No requiere reparar
Python, Visual Studio, Windows ni las protecciones del sistema.

## Corrección

1. Crear una copia independiente de Alpha 2.1.2.
2. Eliminar únicamente `_KERNEL_MODE` de `PreprocessorDefinitions`.
3. Conservar `UNICODE`, `_UNICODE`, `/W4`, `/WX` y el toolset oficial de WDK.
4. Añadir una regresión que prohíbe volver a definir `_KERNEL_MODE`.
5. Ampliar el gate con la tarea
   `Microsoft.DriverKit.Build.Tasks.18.0.dll` observada por MSBuild 18.
6. Mantener los comandos antiguos como wrappers compatibles.
7. No añadir instalación, firma de prueba ni cambios de seguridad.

## Resultado que debe verificarse en Windows

Alpha 2.1.3 debe superar C4117 y continuar compilando `driver.c`. Esto no
promete que no aparezca un error posterior: será la primera compilación real de
todo el archivo con este WDK. Cada error posterior debe analizarse por su causa,
sin desactivar advertencias globalmente.

## Aislamiento

La base estable 2.9.8.9 y Alpha 1, Alpha 2, Alpha 2.1, Alpha 2.1.1 y Alpha
2.1.2 permanecen intactas. No se modifican ViGEmBus, HidHide, Secure Boot,
Integridad de memoria o test signing.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
