# Validación — Nikaido DualSense 3.0.0 Alpha 2.1

Fecha de auditoría: 2026-07-20.

## Resultados portables

| Prueba | Resultado |
| --- | --- |
| Regresiones dirigidas Alpha 1/Alpha 2/Alpha 2.1 | 61 aprobadas, 0 fallos |
| Regresiones nuevas del gate VS2026 | 10 aprobadas, 0 fallos |
| Ruff del comprobador, pruebas y laboratorio | Sin hallazgos |
| Compilación sintáctica dirigida | Correcta |
| Suite completa Alpha 2.1 | 558 aprobadas, 13 bloqueadas por `libEGL.so.1` |
| Suite completa de referencia Alpha 2 | 548 aprobadas, las mismas 13 bloqueadas |

Las 10 pruebas nuevas explican la diferencia entre 548 y 558 aprobadas. Los 13
fallos son idénticos en la copia inmutable de Alpha 2: PySide6 está instalado,
pero el cargador Linux no dispone de `libEGL.so.1`. No se cambió el programa ni
se ocultaron esos fallos mediante reinstalaciones o skips artificiales.

## Cobertura del gate

- Entorno VS2026/WDK 28000 completo simulado: aceptado.
- Integración WDK de MSBuild ausente: bloqueo 23.
- Kit 26100 de la generación VS2022: bloqueo 24.
- Informe JSON sin rutas privadas.
- Proyectos XML válidos, cliente `v145` y driver
  `WindowsKernelModeDriver10.0`.
- Compilación separada de driver y cliente.
- Ausencia de comandos de instalación o debilitamiento de Windows.
- Ausencia de `.sys`, CAT, certificado o paquete HLK distribuido.

## No verificado en este entorno

- Visual Studio 2026, MSBuild y WDK no están disponibles en Linux.
- No se compiló C/C++ ni se generó un `.sys`.
- No se firmó, instaló, cargó o enumeró ningún dispositivo.
- No se ejecutó Driver Verifier, HLK, HVCI, un juego o anti-cheat.
- No se usó un DualSense físico.

La próxima evidencia válida debe ser la salida de
`CHECK_VHF_ALPHA21_ENVIRONMENT.bat` y después `BUILD_VHF_ALPHA21.bat` en el
Windows del usuario. Una compilación correcta seguirá sin autorizar instalación.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
