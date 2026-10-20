# Validación — Nikaido DualSense 3.0.0 Alpha 2.1.4

Fecha: 2026-07-21.

## Resultados portables

| Prueba | Resultado |
| --- | --- |
| Regresiones dirigidas del laboratorio y gate | 68 aprobadas, 0 fallos |
| Suite completa Alpha 2.1.4 | 565 aprobadas, 13 fallos de entorno |
| Ruff de todo el proyecto | Sin hallazgos |
| Compilación sintáctica de todos los `.py` | Correcta |
| Autoprueba del simulador | 12 comprobaciones aprobadas |
| Simulación | 11 reportes aceptados; cierre neutral; 0 salidas al SO |
| JSON y proyectos VCXPROJ | Estructuralmente válidos |
| Integridad de Alpha 2.1.3 | 487 archivos sin cambios respecto al registro previo |

Las regresiones exigen `EnableInf2cat=false` exactamente una vez, prohíben
`RunInf2Cat`, conservan `SignMode=Off`, `/W4` y `/WX`, y verifican que los
lanzadores antiguos redirijan sin recursión a Alpha 2.1.4.

## Fallos de la suite completa

Los 13 fallos ocurren al importar PySide6 porque el contenedor Linux no ofrece
`libEGL.so.1`. Son los mismos 13 fallos ya observados en Alpha 2.1.3 y afectan
solo a pruebas que requieren Qt real: importación GUI, ciclos de `QApplication`,
Profile Studio y fallback visual del Dashboard. No se atribuyen al cambio de
MSBuild/VHF y no se convirtieron en una recomendación de reparar Python o el
runtime.

## Evidencia real recibida de Windows para Alpha 2.1.3

- `ClCompile` terminó con 0 advertencias.
- `Link` generó localmente `NikaidoVirtualHid.sys`.
- `ApiValidator` informó que el driver era Universal.
- El build falló después en `Inf2Cat` con MSB6004 por una ruta de ejecutable no
  válida.
- No se firmó, instaló, cargó ni enumeró ningún driver.

Esta evidencia valida la corrección anterior de `_KERNEL_MODE` y aísla el
nuevo problema, pero no constituye una ejecución de Alpha 2.1.4.

## No verificado en este entorno

- No se ejecutó MSBuild/WDK real sobre Alpha 2.1.4.
- No se confirmó aún en Windows que `Inf2Cat` sea omitido y el cliente compile.
- No se generó, catalogó, firmó, instaló o cargó un paquete distribuible.
- No se enumeró un dispositivo HID.
- No se ejecutaron Driver Verifier, HLK, HVCI, juegos o anti-cheat.
- No se utilizó un DualSense físico.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
