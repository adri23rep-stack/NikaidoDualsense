# Validación — Nikaido DualSense 3.0.0 Alpha 2.1.1

Fecha de auditoría: 2026-07-21.

## Resultados portables

| Prueba | Resultado |
| --- | --- |
| Regresiones dirigidas del laboratorio y gate | 65 aprobadas, 0 fallos |
| Suite completa Alpha 2.1.1 | 562 aprobadas, 13 bloqueadas por `libEGL.so.1` |
| Suite completa de referencia Alpha 2.1 | 558 aprobadas, los mismos 13 bloqueos |
| Ruff de todo el proyecto | Sin hallazgos |
| Compilación sintáctica de todos los `.py` | Correcta |
| Autoprueba del simulador | 12 comprobaciones aprobadas |
| Simulación | 11 reportes aceptados; cierre neutral; 0 salidas al SO |

La diferencia de cuatro pruebas aprobadas corresponde a las nuevas regresiones
del diagnóstico por componente. Los 13 fallos Qt son idénticos en Alpha 2.1:
PySide6 está disponible, pero este contenedor Linux no proporciona
`libEGL.so.1`. No se ocultaron con skips ni se atribuyeron al código nuevo.

## Cobertura nueva

- `vhf.h` ausente se muestra como componente exacto.
- Los otros seis componentes conservan su estado `OK`.
- El JSON usa schema 2 y no contiene rutas privadas.
- Las variables de entorno se resuelven sin depender de mayúsculas.
- Nunca se combinan componentes de dos raíces de kits distintas.
- Los comandos Alpha 2.1 permanecen como wrappers no recursivos.
- No existen comandos de instalación o debilitamiento de Windows.

## No verificado en este entorno

- No hay Windows, Visual Studio 2026, MSBuild o WDK disponibles.
- No se compiló C/C++ ni se generó un `.sys`.
- No se firmó, instaló, cargó o enumeró ningún dispositivo.
- No se ejecutó Driver Verifier, HLK, HVCI, juegos o anti-cheat.
- No se usó un DualSense físico.

La evidencia de Windows recibida demuestra que `vhf.h` falta en el kit local;
no demuestra compilación ni enumeración. El siguiente paso verificable es
ejecutar `CHECK_VHF_ALPHA211_ENVIRONMENT.bat` después de completar el WDK
independiente correspondiente.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
