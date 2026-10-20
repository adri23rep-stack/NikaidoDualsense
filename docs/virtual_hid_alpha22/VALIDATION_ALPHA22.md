# Validación — Nikaido DualSense 3.0.0 Alpha 2.2

## Resultados del entorno disponible

| Comprobación | Resultado |
|---|---|
| SHA-256 del ZIP base Alpha 2.1.5 | Aprobado |
| Integridad ZIP base | Aprobada |
| Árbol base antes de copiar | 501 archivos |
| Pruebas específicas de laboratorio y paquete | 81 aprobadas |
| Regresiones nuevas de paquete Alpha 2.2 | 10 aprobadas |
| Suite completa | 578 aprobadas, 13 fallos de entorno |
| Ruff | Aprobado |
| `compileall` de Python | Aprobado |
| Autoprueba del simulador | 12 comprobaciones aprobadas |
| Simulación | 11 reportes; cierre neutral; 0 reportes al SO |
| Driver fuente frente a Alpha 2.1.5 | Idéntico |
| Fuente estable verificada por `SOURCE_MANIFEST.json` | Aprobada |

## Fallos de la suite completa

Los 13 fallos son los mismos observados en Alpha 2.1.5. PySide6 está instalado,
pero el contenedor Linux no tiene `libEGL.so.1`; por ello fallan imports reales
de Qt y las pruebas offscreen que dependen de `QApplication`. No se convirtieron
en una reparación del runtime ni se clasificaron como errores nuevos de Alpha
2.2.

Las 578 pruebas restantes incluyen el manifiesto estable, codec HID, simulador,
diagnósticos, seguridad, perfiles, Profile Studio mediante pruebas portables y
las nuevas regresiones del empaquetador.

## Cobertura nueva

- Identidad Alpha 2.2 y procedencia Alpha 2.1.5.
- Evidencia de compilación Windows sanitizada.
- Resolución x64 y fallback x86 de herramientas WDK.
- Códigos distintos para `InfVerif` e `Inf2Cat` ausentes.
- Parser PE para driver Native AMD64 sin firma incrustada.
- Rechazo de arquitectura incorrecta o tabla de certificados inesperada.
- Identidad del INF, filtro inferior VHF, catálogo y `DriverVer`.
- Sanitización de rutas, usuario y hostname en salida externa.
- Staging transaccional y eliminación de resultados parciales.
- Ejecución ordenada de `InfVerif /u` antes de `Inf2Cat`.
- Targets x64 y `/uselocaltime` exactos.
- Manifiesto con hashes y estados de seguridad.
- Ausencia de comandos de firma, instalación, elevación o debilitamiento del SO.
- Ausencia de `.sys`, `.cat`, certificados y carpetas `out` en la distribución.

## Evidencia que todavía requiere Windows

Este entorno no dispone de Windows, MSBuild, WDK ni binarios PE reales del
proyecto. Por lo tanto, Alpha 2.2 todavía debe comprobarse mediante:

```bat
CHECK_VHF_ALPHA22_ENVIRONMENT.bat
BUILD_VHF_ALPHA22.bat
PREPARE_VHF_ALPHA22_PACKAGE.bat
```

No se afirma que `InfVerif` o `Inf2Cat` hayan aprobado el INF real en Windows.
Tampoco se realizó firma, instalación, carga, enumeración HID, Driver Verifier,
HVCI, HLK, prueba de juego o prueba con un DualSense físico.

## Estado de seguridad

- Firma: no solicitada.
- Catálogo incluido en la distribución: no.
- Driver incluido en la distribución: no.
- Instalación o carga: no.
- Elevación automática: no.
- Secure Boot, Integridad de memoria y test signing: sin cambios.
- Interfaz principal y emulación estable: sin cambios.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
