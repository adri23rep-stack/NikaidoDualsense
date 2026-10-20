# Validación — Nikaido DualSense 3.0.0 Alpha 2

## Entorno realmente usado

- Sistema: Linux 6.12.47 x86_64.
- Python: 3.12.13.
- pytest: 9.1.1.
- Ruff: 0.15.22.
- Bandit: 1.9.4.
- PySide6 instalado, pero no cargable porque falta `libEGL.so.1` en el sistema.
- Sin Windows, Visual Studio, WDK, MSBuild, InfVerif, Inf2Cat, SignTool, HLK,
  Driver Verifier, juegos, anti-cheat o DualSense físico.

## Resultados

| Prueba | Resultado |
| --- | --- |
| SHA-256 de Alpha 1 | Aprobado; coincidencia exacta |
| Manifiesto heredado de la base estable | 411/411 hashes correctos |
| Compilación sintáctica Python | 177/177 archivos |
| Regresiones portables del laboratorio | 51 aprobadas, 0 fallos |
| Regresiones nuevas específicas de Alpha 2 | 13 aprobadas, 0 fallos |
| Suite completa, sin exclusiones | 548 aprobadas; 13 bloqueadas al cargar Qt |
| Ruff, proyecto completo | 0 hallazgos |
| Bandit, laboratorio Python | 0 hallazgos bajos, medios o altos |
| Tres ciclos consecutivos del simulador | Aprobados; salida idéntica y cierre neutral |
| Descriptor C frente al codec Python | Coincidencia exacta byte por byte |
| Contrato binario | 16 bytes reporte; 32 mensaje; 40 estado |
| XML de proyectos Visual Studio | Bien formado |
| Payload nativo compilado o certificados | 0 archivos |
| Auditoría de privacidad | Aprobada; 0 hallazgos bloqueantes |
| Manifiesto final | 455 entradas verificables; se excluye a sí mismo |

La autoprueba CLI aprobó sus 12 comprobaciones. Cada ciclo simulado aceptó 11
reportes, ejercitó los 14 botones, las ocho direcciones más centro, extremos de
sticks y gatillos analógicos. Los tres ciclos produjeron el mismo SHA-256 de
salida:

`fce5f85659bc92b246ec52b780db3ad6be3a1ce146781bab5c75a1d3919a1e7b`

La historia interna del simulador conservó el digest
`29488744ce18b285e4c6e5bad59319edc7f7da1dfbff7900016dc252804ef578`.
Todos los reportes permanecieron en memoria; ninguno llegó al sistema operativo.

## Cobertura estática de Alpha 2

Las 13 regresiones nuevas comprueban:

- identidad, procedencia y estado bloqueado coherentes;
- nombre de servicio compartido por diagnóstico e INF;
- descriptor HID idéntico al codec portable;
- tamaños y versión del protocolo compartido;
- ciclo `VhfCreate`, `VhfStart`, `VhfReadReportSubmit` y `VhfDelete`;
- timer pasivo de un solo disparo y watchdog de 500 ms;
- dispositivo exclusivo, cola secuencial y neutralización en cierre/energía;
- validación de secuencia, Report ID, D-pad y bits reservados;
- ACL limitada a SYSTEM/administradores y filtro inferior `vhf`;
- VID/PID cero, sin identidad de terceros;
- cliente con SetupAPI, IOCTL y cierre de handle;
- proyectos XML, solución x64 y firma automática desactivada;
- launchers sin comandos de instalación o debilitamiento de Windows;
- ausencia de `.sys`, CAT, certificados y paquetes HLK.

## Suite Qt heredada

El intento completo fue real y usó `QT_QPA_PLATFORM=offscreen`. Trece pruebas
fallaron antes de ejecutar la aplicación porque el cargador de PySide6 no pudo
abrir `libEGL.so.1`. Incluyen importación GUI, tres ciclos de ventana, Profile
Studio, Nuevo/Editar mediante botones y fallbacks de imagen del Dashboard.

No se atribuye ese bloqueo a código de Alpha 2 y no se instaló ni “reparó” un
runtime para ocultarlo. La evidencia Windows reportada previamente por el
usuario pertenece a Alpha 1; no se presenta como una repetición realizada aquí.

## Código nativo no ejecutado

El fuente C/C++ no pudo compilarse ni enlazarse: este entorno no dispone de los
headers y bibliotecas de WDK. Tampoco se ejecutaron InfVerif, Inf2Cat, SignTool,
Driver Verifier o HLK. Las pruebas estáticas encontraron y corrigieron defectos
de diseño, pero no demuestran que el driver cargue o enumere un HID en Windows.

## Errores conocidos y limitaciones

- No hay fallos conocidos del simulador en las pruebas ejecutadas.
- El backend nativo permanece bloqueado intencionalmente.
- El fuente KMDF/VHF puede contener defectos que sólo detecten MSBuild, análisis
  de drivers, Driver Verifier o pruebas PnP reales.
- No se verificó instalación, actualización, eliminación, suspensión, HVCI,
  Secure Boot, firma, GameInput, Steam Input, juegos o anti-cheat.
- El dispositivo propuesto es un gamepad HID genérico, no un DualSense completo.
- No existen salidas virtuales de vibración, háptica, luz, audio, movimiento,
  touch multipunto o gatillos adaptativos.
- No se hicieron pruebas físicas USB/Bluetooth ni se modificó Windows.

© Team Nikaido
