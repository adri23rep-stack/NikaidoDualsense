# Validación — Nikaido DualSense 3.0.0 Alpha 2.2.3

## Resultados del entorno disponible

| Comprobación | Resultado |
|---|---|
| SHA-256 del ZIP base Alpha 2.2.2 | Aprobado |
| Manifiesto de la base Alpha 2.2.2 | 527 archivos, 0 diferencias |
| Regresiones de paquete Alpha 2.2.3 | 18 aprobadas |
| Pruebas específicas de laboratorio | 89 aprobadas |
| Suite completa | 586 aprobadas, 13 fallos de entorno |
| Ruff | Aprobado |
| Compilación sintáctica de Python | Aprobada |
| Autoprueba del simulador | 12 comprobaciones aprobadas |
| Simulación | 11 reportes; cierre neutral; 0 reportes al SO |
| `driver.c` frente a Alpha 2.2.2 | Idéntico |
| Protocolo VHF frente a Alpha 2.2.2 | Idéntico |
| Manifiesto estable `SOURCE_MANIFEST.json` | Aprobado |
| Auditoría de privacidad del árbol | Aprobada, 536 archivos y 0 bloqueos |
| Validación profunda del ZIP | Aprobada, 536 archivos |
| Auditoría de privacidad del ZIP | Aprobada, 0 bloqueos |

La validación profunda comprobó integridad CRC, una sola raíz, ausencia de
rutas inseguras, duplicados, enlaces simbólicos, cachés, temporales, binarios
nativos generados, registros de build y certificados. Los 535 archivos
descritos por el manifiesto interno coincidieron en tamaño y SHA-256; el
archivo 536 es el propio manifiesto.

## Cobertura nueva

- Reproducción portable del formato observado: imagen ejecutable Native x64 sin
  `IMAGE_FILE_SYSTEM`.
- Aceptación con el bit descriptivo presente o ausente.
- Rechazo de imágenes sin `IMAGE_FILE_EXECUTABLE_IMAGE`.
- Rechazo de imágenes sin secciones o sin punto de entrada.
- Conservación del rechazo por arquitectura, formato, subsistema o firma
  inesperados.
- Registro esquema 2 con resultado PE sanitizado.
- Registro por hashes, `InfVerif`, `Inf2Cat` y staging transaccional intactos.
- Wrappers antiguos redirigidos directamente a Alpha 2.2.3.
- Ausencia de firma, instalación, elevación o cambios de seguridad.

## Fallos de la suite completa

Los 13 fallos son los mismos de Alpha 2.2.2. PySide6 está instalado, pero el
contenedor Linux no contiene `libEGL.so.1`; por ello fallan imports Qt y las
pruebas offscreen que requieren `QApplication`, Profile Studio o Dashboard.
Las otras 586 pruebas aprobaron. No se convirtió este faltante del contenedor
en una reparación del runtime de Windows ni se clasificó como regresión.

## Evidencia que todavía requiere Windows

Alpha 2.2.3 no se compiló ni ejecutó en Windows dentro de este entorno. La
validación pendiente es:

```bat
CHECK_VHF_ALPHA223_ENVIRONMENT.bat
BUILD_VHF_ALPHA223.bat
PREPARE_VHF_ALPHA223_PACKAGE.bat
```

La evidencia comunicada de Alpha 2.2.2 sí confirma una compilación real con
0 advertencias y 0 errores. También confirma que la regla
`IMAGE_FILE_SYSTEM` bloqueaba antes de generar el registro. Alpha 2.2.3 corrige
esa regla, pero no se afirma que `InfVerif` o `Inf2Cat` hayan aprobado todavía
esta nueva copia.

## No realizado

- Firma de catálogo o driver.
- Instalación, carga o enumeración HID.
- Driver Verifier, HVCI, HLK o WHCP.
- Pruebas de suspensión y reanudación.
- Pruebas con un DualSense físico, `joy.cpl`, juegos o anti-cheat.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
