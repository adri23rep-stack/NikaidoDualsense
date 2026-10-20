# Validación — Nikaido DualSense 3.0.0 Alpha 1

## Entorno realmente usado

- Sistema: Linux 6.12.47 x86_64.
- Python: 3.12.13.
- PySide6: 6.8.3 instalado en el entorno de auditoría.
- pytest: 9.1.1.
- Ruff: 0.15.22.
- Bandit: 1.9.4.
- Sin Windows, WDK, HLK, firma de drivers, juegos, anti-cheat ni DualSense
  físico.

## Resultados

| Prueba | Resultado |
| --- | --- |
| SHA-256 del ZIP oficial | Aprobado; coincidencia exacta |
| Seguridad estructural del ZIP oficial | 442 entradas; 0 rutas inseguras, symlinks o duplicados |
| Manifiesto estable | 411/411 hashes correctos |
| Inmutabilidad de la base en Alpha 1 | 412/412 archivos originales idénticos |
| Compilación sintáctica final | 176/176 archivos Python |
| Importación de módulos no GUI y laboratorio | 47/47 |
| Ruff, proyecto activo | 0 hallazgos |
| Bandit, laboratorio nuevo | 0 hallazgos bajos, medios o altos |
| Bandit, proyecto completo sin tests/legacy | 102 bajos preexistentes; 0 medios; 0 altos |
| Regresiones nuevas Alpha 1 | 38 aprobadas, 0 fallos |
| Suite completa, intento sin exclusiones | 535 aprobadas, 13 fallos de carga Qt |
| Suite ejecutable en este entorno | 535 aprobadas, 13 deseleccionadas por bloqueo Qt |
| Perfiles, `.Nika` y migración, subconjunto portable | 38 aprobadas |
| Medios de perfil portables | 5 aprobadas, 2 Qt deseleccionadas |
| Autoprueba CLI | 12/12 comprobaciones aprobadas |
| Tres ciclos de inicio/cierre del simulador | Aprobados |
| Auditoría de privacidad | Aprobada; 0 hallazgos bloqueantes |

## Cobertura nueva de Alpha 1

Las 38 regresiones validan:

- identidad independiente y versión estable sin relabel;
- modelo inmutable, alias documentados y rechazo de valores inválidos, NaN e
  infinitos;
- los 14 botones solicitados;
- las ocho direcciones del D-pad y el centro;
- extremos y round-trip de ambos sticks;
- rango completo y round-trip de L2/R2;
- longitud, Report ID y bits reservados del reporte genérico;
- inicio idempotente, tres ciclos consecutivos y cierre neutral;
- rechazo de secuencias obsoletas sin corrupción;
- callbacks defectuosos, desuscripción idempotente y límite del historial;
- fallo inyectado con neutralización segura;
- 80 actualizaciones desde cuatro productores concurrentes;
- diagnóstico sanitizado y política de cero mutaciones;
- backend nativo sellado;
- comandos CLI, exportación JSON atómica y launcher independiente;
- ausencia de imports desde la aplicación estable;
- hashes del manifiesto estable.

La simulación determinista aceptó 11 reportes, ejercitó todos los controles,
realizó dos neutralizaciones y terminó en estado `stopped` y neutral. Su digest
de reportes fue
`29488744ce18b285e4c6e5bad59319edc7f7da1dfbff7900016dc252804ef578`.
Los reportes permanecieron en memoria y no llegaron al sistema operativo.

## Profile Studio y Dashboard

En este entorno pasaron 38 pruebas portables de catálogo, ocho perfiles
incluidos, aplicación sin hardware, restauración, alias heredados, migración,
importación/exportación `.Nika`, paquetes dañados y configuración corrupta.
También pasaron cinco pruebas portables de iconos, banners y compatibilidad de
rutas antiguas.

Las pruebas Qt reales de construir ventanas, pulsar Nuevo/Editar, abrir Profile
Studio y renderizar fallbacks del Dashboard no pudieron iniciarse: la biblioteca
Qt requiere `libEGL.so.1`, ausente en el contenedor. El intento se hizo con
`QT_QPA_PLATFORM=offscreen`; 13 casos fallaron todos en el mismo import de Qt,
antes de ejecutar código de la aplicación.

La base incluye su propia evidencia histórica
`docs/history/validations/VALIDACION_2.9.8.9.md`, donde esos casos pasaron con
PySide6 offscreen. Esa evidencia se preserva, pero no se presenta como una
repetición realizada aquí.

## Errores conocidos y limitaciones

- No hay fallos conocidos del backend simulado en las pruebas ejecutadas.
- El backend nativo está bloqueado intencionalmente; no existe un dispositivo
  HID virtual visible para Windows.
- No se ejecutaron pruebas físicas, USB, Bluetooth, audio, ViGEm, HidHide,
  bandeja real, instalador, firma ni arranques como procesos Windows separados.
- No se verificó compatibilidad con juegos, GameInput, Steam Input, anti-cheat o
  protocolo DualSense.
- La GUI estable no pudo volver a verificarse en este Linux por la dependencia
  de sistema `libEGL.so.1`; no se intentó convertirlo en una reparación del
  runtime del proyecto.
- La deuda estática preexistente de excepciones amplias y acoplamiento GUI quedó
  documentada y sin cambios por la condición de rama inmutable.

## Interpretación correcta

`Simulado` significa que el contrato, los reportes y el ciclo de vida funcionan
en memoria. `Bloqueado` significa que no se compiló, instaló ni cargó un driver.
Nada de esta validación demuestra una emulación DualSense real en Windows.

© Team Nikaido
