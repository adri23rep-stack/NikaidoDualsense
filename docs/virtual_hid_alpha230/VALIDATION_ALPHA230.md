# Validación — Nikaido DualSense 3.0.0 Alpha 2.3.0

Fecha de cierre: 23 de julio de 2026.

## Resultado

La implementación portable de Alpha 2.3.0 quedó validada. El flujo real de
Windows permanece pendiente: este entorno no puede ejecutar MSBuild/WDK,
MakeCab, SignTool, Partner Center ni un driver KMDF.

| Comprobación | Resultado |
|---|---|
| Integridad del ZIP base Alpha 2.2.3 | 535/535 entradas válidas |
| Regresiones de paquete, firma y laboratorio | 101 aprobadas |
| Suite completa | 598 aprobadas; 13 bloqueadas por `libEGL.so.1` ausente |
| Ruff sobre todo el proyecto | Aprobado |
| Compilación sintáctica de todos los Python | Aprobada |
| Autoprueba del simulador | 12/12 aprobadas |
| Secuencia simulada | 11 reportes; cierre neutral; 0 reportes al SO |
| Diagnóstico portable | Aprobado; backend nativo bloqueado |
| Detección local de MakeCab/SignTool | Bloqueada correctamente fuera de Windows |

## Entorno realmente usado

- Linux x64.
- Python 3.12.13 para las pruebas del laboratorio.
- Pytest 9.1.1.
- PySide6 6.8.3 presente, pero no cargable por falta de `libEGL.so.1`.
- Ruff 0.15.22.

No se realizaron pruebas en Windows, con WDK, con un driver cargado, con
Partner Center, con HLK, con Driver Verifier ni con un DualSense físico.

## Suite completa

Comando:

```console
python -m pytest -q
```

Resultado:

```text
598 passed, 13 failed
```

Los 13 fallos tienen la misma causa externa: PySide6 está instalado, por lo que
las pruebas Qt intentan ejecutarse, pero el cargador de Linux no encuentra
`libEGL.so.1`. Afectan importación Qt, construcción offscreen, Dashboard y
Profile Studio. No son regresiones distintas detectadas en Alpha 2.3.0 y no se
convirtieron en una reparación de runtime.

La misma categoría y cantidad de fallos ya existía en la base Alpha 2.2.3. Las
pruebas portables que cubren la nueva versión se ejecutaron separadamente y
aprobaron en su totalidad.

## Regresiones específicas

Comando:

```console
python -m pytest -q tests/test_driver_package_alpha230.py tests/test_signing_readiness_alpha230.py tests/test_virtual_hid_alpha2_source.py tests/test_vs2026_toolchain_alpha21.py tests/test_virtual_dualsense_lab_alpha1.py
```

Resultado:

```text
101 passed
```

Cobertura añadida:

- herramientas localizadas sin inspeccionar certificados;
- PDB incluido en el registro por hashes;
- bloqueo de marcadores privados;
- DDF temporal y estructura exacta del CAB;
- lectura y rechazo de tablas CAB inválidas;
- manifiesto sanitizado;
- continuidad del contenido PE a través de una firma simulada;
- rechazo de cambios en una sección del SYS;
- verificación con `/kp` y pertenencia al catálogo;
- ausencia de comandos de firma, instalación o carga;
- invalidación del CAB o manifiesto local alterados;
- wrappers y metadatos de Alpha 2.3.0.

## Comprobaciones adicionales

```console
ruff check .
python -m compileall -q .
python -m virtual_dualsense_lab self-test
python -m virtual_dualsense_lab simulate
python -m virtual_dualsense_lab diagnose --json
python native/vhf/tools/signing_readiness.py check-tools --json
```

El último comando terminó con código 60 porque MakeCab y SignTool no existen en
Linux. El informe indicó que no consultó certificados, no cargó claves y no
realizó mutaciones. Este es el bloqueo esperado, no un fallo del código
portable.

## Continuidad de la base

Los archivos que definen la implementación VHF permanecen idénticos a Alpha
2.2.3:

| Archivo | SHA-256 en Alpha 2.2.3 y Alpha 2.3.0 |
|---|---|
| `native/vhf/driver/driver.c` | `ca547072b70c12766cceeb570b6c3bbb6e53a51369bc5a1346db9868072f0473` |
| `native/vhf/shared/nikaido_vhf_protocol.h` | `88500ac62d7a3fae2e24ca5a808e13be16b24324a1580a745cc2c73ddc519689` |
| `SOURCE_MANIFEST.json` | `dac86adb96f5da531e303e1aa3f6fbff8207e0c1a604d0fa413a3c030f5e5fb9` |

No se modificaron la emulación estable, el descriptor HID, los perfiles,
configuraciones ni la interfaz principal.

## Evidencia de Windows heredada

La última ejecución real comunicada corresponde a Alpha 2.2.3:

- driver y cliente compilados con 0 advertencias y 0 errores;
- InfVerif Universal aprobado;
- Inf2Cat aprobado con 0 errores y 0 advertencias;
- CAT sin firma generado;
- ningún driver firmado, instalado o cargado.

Alpha 2.3.0 debe repetirse desde el principio en Windows. No se trasladan
binarios generados de Alpha 2.2.3 porque el INF, la versión del proyecto y el
registro de hashes cambiaron.

## Errores conocidos

- Las 13 pruebas Qt no pueden ejecutarse en este contenedor por falta de
  `libEGL.so.1`.
- La creación real del CAB con MakeCab aún no fue ejecutada en Windows.
- La verificación real con SignTool aún no puede ejecutarse porque no existe una
  respuesta firmada de Microsoft.

## Limitaciones funcionales

- El ZIP no incluye SYS, CAT, PDB o CAB.
- No existe firma aceptada por Microsoft.
- No se instala ni enumera ningún dispositivo.
- El backend Python nativo continúa sellado.
- No se afirma compatibilidad con DualSense, juegos, anti-cheat, HVCI o
  suspensión/reanudación.
- Háptica, audio, luces, movimiento, coordenadas de touchpad y gatillos
  adaptativos virtuales permanecen fuera del alcance.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
