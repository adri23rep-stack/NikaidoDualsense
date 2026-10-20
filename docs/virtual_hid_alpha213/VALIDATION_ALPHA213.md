# Validación — Nikaido DualSense 3.0.0 Alpha 2.1.3

Fecha de auditoría: 2026-07-21.

## Resultados portables

| Prueba | Resultado |
| --- | --- |
| Regresiones dirigidas del laboratorio y gate | 68 aprobadas, 0 fallos |
| Suite completa Alpha 2.1.3 | 565 aprobadas, 13 fallos por `libEGL.so.1` |
| Suite completa de referencia Alpha 2.1.2 | 564 aprobadas, los mismos 13 fallos |
| Ruff de todo el proyecto | Sin hallazgos |
| Compilación sintáctica de todos los `.py` | Correcta |
| Autoprueba del simulador | 12 comprobaciones aprobadas |
| Simulación | 11 reportes aceptados; cierre neutral; 0 salidas al SO |
| Gate con estructura WDK 28000 simulada | Listo, salida 0 |
| JSON y proyectos VCXPROJ | Estructuralmente válidos |

La regresión nueva reproduce la tarea de WDK ausente y otra verifica que el
proyecto no defina `_KERNEL_MODE`, mantenga `UNICODE`/`_UNICODE` y conserve
`TreatWarningAsError=true`.

Los 13 fallos Qt son idénticos a Alpha 2.1.2. El contenedor Linux permite
resolver PySide6, pero no proporciona `libEGL.so.1`; por ello no puede crear
`QApplication`, construir ventanas ni ejecutar Profile Studio. No se atribuyen
estos fallos al cambio del proyecto VHF.

## Evidencia real recibida de Windows

- Alpha 2.1.2 detectó MSBuild 18.8.2, v145, integración WDK, kit 28000 y
  bibliotecas Spectre.
- MSBuild cargó las tareas del WDK, preparó el INF e inició `ClCompile`.
- El compilador emitió C4117 porque el proyecto redefinía `_KERNEL_MODE`.
- `/WX` convirtió esa advertencia en C2220.
- No se instaló ni cargó ningún resultado parcial.

Esa evidencia valida el diagnóstico, pero no constituye una compilación de
Alpha 2.1.3.

## No verificado en este entorno

- No se ejecutó MSBuild/WDK real sobre Alpha 2.1.3.
- No se generó, firmó, instaló o cargó un `.sys`.
- No se enumeró un dispositivo HID.
- No se ejecutaron Driver Verifier, HLK, HVCI, juegos o anti-cheat.
- No se utilizó un DualSense físico.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
