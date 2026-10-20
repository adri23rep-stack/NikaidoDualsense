# Validación — Nikaido DualSense 3.0.0 Alpha 2.2.1

## Resultados del entorno disponible

| Comprobación | Resultado |
|---|---|
| SHA-256 del ZIP base Alpha 2.2 | Aprobado |
| Manifiesto de la base Alpha 2.2 | 511 archivos, 0 diferencias |
| Regresiones de paquete Alpha 2.2.1 | 13 aprobadas |
| Pruebas específicas de laboratorio | 84 aprobadas |
| Suite completa | 581 aprobadas, 13 fallos de entorno |
| Ruff | Aprobado |
| Compilación sintáctica de Python | Aprobada |
| Autoprueba del simulador | 12 comprobaciones aprobadas |
| Simulación | 11 reportes; cierre neutral; 0 reportes al SO |
| `driver.c` frente a Alpha 2.2 | Idéntico |
| Protocolo VHF frente a Alpha 2.2 | Idéntico |
| Manifiesto estable `SOURCE_MANIFEST.json` | Aprobado |
| Auditoría de privacidad del árbol | Aprobada, 0 bloqueos |
| Validación profunda del ZIP | Aprobada, 520 archivos |
| Auditoría de privacidad del ZIP | Aprobada, 0 bloqueos |

La validación del ZIP comprobó integridad CRC, una sola raíz, ausencia de rutas
inseguras, duplicados, enlaces simbólicos, cachés, temporales, binarios nativos
generados y certificados. Los 519 archivos descritos por el manifiesto interno
coincidieron en tamaño y SHA-256; el archivo 520 es el propio manifiesto.

## Cobertura nueva

- Disposición observada: kit de compilación 28000 con `Inf2Cat` 26100 x86.
- Preferencia de `Inf2Cat` del kit seleccionado cuando existe.
- Fallback restringido a la misma raíz Windows Kits.
- Exclusión de versiones anteriores al build mínimo aceptado.
- Registro separado del kit de compilación, `InfVerif` e `Inf2Cat`.
- Conservación del campo histórico `kit_version` en el manifiesto de paquete.
- Lista completa de destinos entregada a `Inf2Cat`.
- Ausencia de rutas absolutas en informes serializados.
- Staging transaccional y eliminación ante rechazo.
- Ausencia de firma, instalación, elevación o cambios de seguridad.

## Fallos de la suite completa

Los 13 fallos se deben a que PySide6 está instalado pero el contenedor Linux no
contiene `libEGL.so.1`. Afectan imports Qt, `QApplication` offscreen, Profile
Studio y Dashboard. Son los mismos 13 fallos de entorno documentados en Alpha
2.2; las 581 pruebas restantes aprobaron. No se clasificó este faltante del
contenedor como un error del código ni se convirtió en una reparación del
runtime de Windows.

El auditor de privacidad estable interpreta el nombre genérico del directorio
HOME del contenedor como coincidencia con etiquetas XML que contienen
`RootNamespace`. La auditoría distribuida se ejecutó con una identidad neutra
de prueba; permanecieron activas las reglas generales para rutas de usuario de
Windows y POSIX. El resultado fue 0 bloqueos y 0 avisos.

## Evidencia que todavía requiere Windows

Este entorno no dispone de Windows, MSBuild, WDK ni los binarios Release x64
generados en el equipo de prueba. Por ello no se afirma haber ejecutado
`InfVerif` o `Inf2Cat` sobre el paquete real de Alpha 2.2.1.

La validación pendiente es:

```bat
CHECK_VHF_ALPHA221_ENVIRONMENT.bat
BUILD_VHF_ALPHA221.bat
PREPARE_VHF_ALPHA221_PACKAGE.bat
```

El resultado verificable esperado es código cero y la carpeta
`native\vhf\out\NikaidoVhfA221`. Si `Inf2Cat` 26100 no reconoce uno de los
destinos solicitados, el preparador devolverá código 47 y no publicará un
paquete parcial.

## No realizado

- Firma de catálogo o driver.
- Instalación, carga o enumeración HID.
- Driver Verifier, HVCI, HLK o WHCP.
- Pruebas de suspensión/reanudación.
- Pruebas con un DualSense físico, juegos, `joy.cpl` o anti-cheat.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
