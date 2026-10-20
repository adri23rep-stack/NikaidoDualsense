# Validación — Nikaido DualSense 3.0.0 Alpha 2.2.2

## Resultados del entorno disponible

| Comprobación | Resultado |
|---|---|
| SHA-256 del ZIP base Alpha 2.2.1 | Aprobado |
| Manifiesto de la base Alpha 2.2.1 | 519 archivos, 0 diferencias |
| Regresiones de paquete Alpha 2.2.2 | 18 aprobadas |
| Pruebas específicas de laboratorio | 89 aprobadas |
| Suite completa | 586 aprobadas, 13 fallos de entorno |
| Ruff | Aprobado |
| Compilación sintáctica de Python | Aprobada |
| Autoprueba del simulador | 12 comprobaciones aprobadas |
| Simulación | 11 reportes; cierre neutral; 0 reportes al SO |
| `driver.c` frente a Alpha 2.2.1 | Idéntico |
| Protocolo VHF frente a Alpha 2.2.1 | Idéntico |
| Manifiesto estable `SOURCE_MANIFEST.json` | Aprobado |
| Auditoría de privacidad del árbol | Aprobada, 528 archivos y 0 bloqueos |
| Validación profunda del ZIP | Aprobada, 528 archivos |
| Auditoría de privacidad del ZIP | Aprobada, 0 bloqueos |

La validación profunda comprobó integridad CRC, una sola raíz, ausencia de
rutas inseguras, duplicados, enlaces simbólicos, cachés, temporales, binarios
nativos generados, registros de build y certificados. Los 527 archivos
descritos por el manifiesto interno coincidieron en tamaño y SHA-256; el
archivo 528 es el propio manifiesto.

## Cobertura nueva

- El registro anterior se invalida antes de comprobar o ejecutar MSBuild.
- Un build fallido no puede reutilizar el comprobante anterior.
- El comprobante solo se escribe después de compilar driver y cliente.
- El registro usa rutas relativas, tamaños y SHA-256.
- Las fechas de extracción, zona horaria y reloj no participan en la decisión.
- Una fuente con fecha futura es aceptada si su contenido coincide.
- Una fuente o un SYS modificados después del build son rechazados.
- Un registro ausente, dañado, incompleto, duplicado o de otra versión bloquea.
- La validación PE, `InfVerif`, `Inf2Cat` y el staging transaccional permanecen.
- No se añadieron firma, instalación, elevación ni cambios de seguridad.

## Fallos de la suite completa

Los 13 fallos son los mismos de Alpha 2.2.1. PySide6 está instalado, pero el
contenedor Linux no contiene `libEGL.so.1`; por ello fallan imports Qt y las
pruebas offscreen que requieren `QApplication`, Profile Studio o Dashboard.
Las otras 586 pruebas aprobaron. Este faltante del contenedor no se convirtió
en una reparación del runtime de Windows ni se clasificó como regresión.

## Evidencia que todavía requiere Windows

Alpha 2.2.2 no se compiló ni ejecutó en Windows dentro de este entorno. La
validación pendiente es:

```bat
CHECK_VHF_ALPHA222_ENVIRONMENT.bat
BUILD_VHF_ALPHA222.bat
PREPARE_VHF_ALPHA222_PACKAGE.bat
```

La evidencia comunicada de Alpha 2.2.1 sí confirma que driver y cliente
compilaron con 0 advertencias y 0 errores, y que se detectaron `InfVerif` 28000
x64 e `Inf2Cat` 26100 x86. Alpha 2.2.2 corrige el bloqueo posterior, pero no se
afirma que `InfVerif` o `Inf2Cat` hayan aprobado todavía esta nueva copia.

## No realizado

- Firma de catálogo o driver.
- Instalación, carga o enumeración HID.
- Driver Verifier, HVCI, HLK o WHCP.
- Pruebas de suspensión y reanudación.
- Pruebas con un DualSense físico, `joy.cpl`, juegos o anti-cheat.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
