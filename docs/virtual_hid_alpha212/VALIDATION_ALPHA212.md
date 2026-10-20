# Validación — Nikaido DualSense 3.0.0 Alpha 2.1.2

Fecha de auditoría: 2026-07-21.

## Resultados portables

| Prueba | Resultado |
| --- | --- |
| Regresiones dirigidas del laboratorio y gate | 67 aprobadas, 0 fallos |
| Suite completa Alpha 2.1.2 | 564 aprobadas, 13 fallos por `libEGL.so.1` |
| Suite completa de referencia Alpha 2.1.1 | 562 aprobadas, los mismos 13 fallos |
| Ruff de todo el proyecto | Sin hallazgos |
| Compilación sintáctica de todos los `.py` | Correcta |
| Autoprueba del simulador | 12 comprobaciones aprobadas |
| Simulación | 11 reportes aceptados; cierre neutral; 0 salidas al SO |
| Gate con estructura WDK 28000 simulada | Listo, salida 0 |

Las dos regresiones nuevas verifican la ruta real `shared\vhf.h` y bloquean una
regresión a la ruta `km\vhf.h`. Los 13 fallos Qt son idénticos a Alpha 2.1.1:
este contenedor Linux no incluye `libEGL.so.1`.

## Evidencia real recibida de Windows

- MSBuild 18.8.2 y Visual Studio 2026 detectados.
- `v145`, integración WDK y Spectre x64 detectados.
- SDK y WDK 28000.1 registrados.
- `vhf.h` presente bajo `shared` en las familias 22621, 26100 y 28000.

Esta evidencia valida la corrección de la ruta, pero Alpha 2.1.2 todavía debe
ejecutarse en Windows. No se presenta como compilación del driver.

## No verificado en este entorno

- No se ejecutaron MSBuild o WDK reales.
- No se generó, firmó, instaló o cargó un `.sys`.
- No se enumeró un dispositivo HID.
- No se ejecutaron Driver Verifier, HLK, HVCI, juegos o anti-cheat.
- No se utilizó un DualSense físico.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
