# Diagnóstico y plan — Alpha 2.1.4

Fecha: 2026-07-21.

## Evidencia real de Windows

La compilación de Alpha 2.1.3 aportada por el usuario confirmó, sin incluir
rutas privadas en este informe, lo siguiente:

- MSBuild 18.8.2, Visual Studio 2026, MSVC `v145` y WDK/SDK 28000 fueron
  detectados correctamente;
- `driver.c` terminó `ClCompile` con `/W4` y `/WX`, sin advertencias;
- el enlazador generó localmente `NikaidoVirtualHid.sys`;
- `ApiValidator` aceptó el binario como driver Universal;
- la preparación del paquete copió el INF;
- el objetivo posterior `Inf2Cat` falló con MSB6004 porque el ejecutable x86
  indicado por WDK no existía;
- MSBuild no inició la compilación del cliente porque el primer proyecto
  devolvió error;
- no hubo firma, instalación, carga ni enumeración del driver.

## Causa

Alpha 2.1.3 declaró `RunInf2Cat=false`. Esa propiedad no impidió que las tareas
de WDK 28000 ejecutaran el objetivo `Inf2Cat`. La propiedad de proyecto que
controla esa etapa es `EnableInf2cat`; por ello el build llegó correctamente
hasta después del enlace y falló en una herramienta de empaquetado.

El error no pertenece a `driver.c`, Python, el runtime estable ni las
protecciones de Windows. Tampoco justifica instalar o reparar componentes para
el objetivo limitado de Alpha 2.1.4, que es compilar fuente sin producir un
paquete instalable.

## Corrección mínima y mantenible

1. Crear una copia independiente de Alpha 2.1.3.
2. Reemplazar únicamente `RunInf2Cat=false` por `EnableInf2cat=false`.
3. Conservar `SignMode=Off`, `/W4`, `/WX`, el toolset de kernel y toda la lógica
   KMDF/VHF.
4. Añadir regresiones que exijan la propiedad correcta y prohíban la antigua.
5. Mantener los comandos anteriores como wrappers de compatibilidad.
6. Documentar la evidencia real y distinguir compilación, catálogo, firma,
   instalación y enumeración.

## Resultado esperado en Windows

`BUILD_VHF_ALPHA214.bat` debe terminar el proyecto del driver sin invocar
`Inf2Cat` y después iniciar el proyecto del cliente. Aunque ambos proyectos
compilen, el resultado seguirá siendo local, sin catálogo y sin firma; no debe
instalarse.

## Aislamiento y seguridad

La base estable 2.9.8.9 y todas las Alphas anteriores permanecen intactas. La
copia no importa ni modifica ViGEmBus, HidHide o la interfaz principal. No
incluye instalación automática, elevación, certificados, `pnputil`, `devcon`,
`bcdedit` ni cambios de Secure Boot, HVCI o test signing.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
