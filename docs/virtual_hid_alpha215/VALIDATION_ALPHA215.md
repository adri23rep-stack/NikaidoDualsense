# Validación — Nikaido DualSense 3.0.0 Alpha 2.1.5

Fecha: 2026-07-22.

## Resultados portables

| Prueba | Resultado |
| --- | --- |
| Regresiones dirigidas del laboratorio y cliente | 71 aprobadas, 0 fallos |
| Suite completa Alpha 2.1.5 | 568 aprobadas, 13 fallos de entorno |
| Ruff de todo el proyecto | Sin hallazgos |
| Compilación sintáctica de todos los `.py` | Correcta |
| Autoprueba del simulador | 12 comprobaciones aprobadas |
| Simulación | 11 reportes aceptados; cierre neutral; 0 salidas al SO |
| Driver `driver.c` frente a Alpha 2.1.4 | SHA-256 idéntico |
| JSON y proyectos VCXPROJ | Estructuralmente válidos |

Las tres regresiones nuevas comprueban:

1. captura del error antes de limpiar SetupAPI y transporte explícito hasta
   `wmain`;
2. salida mediante `WriteConsoleW` o UTF-8, sin `wprintf`/`fwprintf`;
3. inmutabilidad de `driver.c` mediante SHA-256.

## Fallos de la suite completa

Los 13 fallos ocurren al importar PySide6 porque el contenedor Linux no ofrece
`libEGL.so.1`. Son los mismos fallos documentados en Alpha 2.1.4 y afectan a
pruebas GUI reales: importación, ciclos de `QApplication`, Profile Studio y
fallbacks visuales del Dashboard. No se atribuyen al cliente VHF ni se
convierten en una recomendación de reparar Python o el runtime.

## Evidencia real recibida de Windows para Alpha 2.1.4

- Driver y cliente Release x64 presentes.
- Driver SHA-256:
  `56bb31026349e19d4711e93d69073d0e172fb897acbd1ef34c1456f6d004d4ad`.
- Cliente SHA-256:
  `abe9a22e06cdb43fdec1bd64109ab6ca0662d6cc0d4e2dfb50e70f4e0d64f123`.
- `status` devolvió código `3`, no abrió interfaz y mostró incorrectamente
  `error 0`.
- No hubo instalación, carga o enumeración.

## No verificado en este entorno

- No se compiló el C++ de Alpha 2.1.5 con MSVC/WDK.
- No se ejecutó el cliente corregido en Windows.
- No se confirmó todavía el error Win32 no nulo ni la presentación Unicode.
- No se generó, catalogó, firmó, instaló o cargó un paquete distribuible.
- No se enumeró un dispositivo HID.
- No se ejecutaron Driver Verifier, HLK, HVCI, juegos o anti-cheat.
- No se utilizó un DualSense físico.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
