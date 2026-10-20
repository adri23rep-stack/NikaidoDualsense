# Auditoría y diagnóstico — Virtual DualSense Lab Alpha 1

## Resultado ejecutivo

La base oficial 2.9.8.9 es válida y quedó inmutable. Alpha 1 se construyó como
una copia completa y separada que solo agrega un laboratorio portable. No se
modificó, sustituyó, importó ni envolvió el sistema actual de emulación.

La investigación confirma que un mando HID genérico es técnicamente viable en
Windows mediante VHF o UDE, pero un DualSense virtual real no puede reducirse a
un módulo Python ni a un descriptor HID. Requiere un driver de modo kernel, un
paquete firmado y pruebas específicas de Windows. Este entorno Linux no tiene
WDK, HLK, firma, una máquina Windows de prueba ni hardware físico. Por ello, el
backend nativo está sellado y Alpha 1 entrega el diagnóstico, la arquitectura,
el codec genérico y un backend simulado totalmente verificable.

## Procedencia e integridad de la base

| Comprobación | Resultado |
| --- | --- |
| Archivo oficial | `Nikaido_DualSense-2.9.8.9-Beta1-Stability-Audit.zip` |
| SHA-256 esperado | `14ea6788a36b620ec907a508c67e307aad8ccbec5a6235ba199e5e5910a29338` |
| SHA-256 calculado | Coincidencia exacta |
| Tamaño | 8,801,251 bytes |
| Estructura ZIP | 442 entradas, 412 archivos |
| Rutas absolutas/traversal | 0 |
| Enlaces simbólicos | 0 |
| Entradas duplicadas | 0 |
| Prueba integral del ZIP | Aprobada |
| `SOURCE_MANIFEST.json` | 411/411 archivos presentes y con hash correcto |
| SHA-256 del manifiesto de origen | `dac86adb96f5da531e303e1aa3f6fbff8207e0c1a604d0fa413a3c030f5e5fb9` |

El ZIP oficial se conservó con permisos de solo lectura y la referencia
extraída con cero archivos escribibles. La comparación final verifica todos los
archivos originales por hash, no solo por nombre o fecha.

## Alcance revisado antes de agregar el laboratorio

Se recorrieron los 412 archivos del proyecto, incluidos código, pruebas,
launchers, instaladores, configuración, perfiles, recursos y documentación.
La base contiene 164 archivos Python y 63,540 líneas Python.

- Compilación sintáctica inicial: 164/164.
- Ruff inicial: cero hallazgos en el código activo.
- Importaciones locales sin resolver por análisis estático: cero.
- Definiciones duplicadas en un mismo ámbito: cero.
- Uso de `shell=True`: cero.
- Bandit: cero hallazgos medios o altos; 102 bajos preexistentes.
- Manejadores `except Exception` preexistentes: 267.
- Ciclos estáticos: uno en la capa GUI, entre exports y referencias de
  `gui.assistant`, `gui.components`, `gui.main_window`, páginas y
  `gui.profile_visuals`.

Los 267 manejadores amplios y el ciclo estático son deuda de mantenibilidad,
pero no justifican alterar una rama declarada inmutable. Muchos manejadores
están en rutas de cierre, fallbacks de plataforma o herramientas. Deben
revisarse por subsistema en una rama posterior, con pruebas Windows, en lugar
de cambiarse masivamente.

## Arquitectura estable observada

1. Los launchers comprueban dependencias con
   `tools/check_runtime_dependencies.py` antes de importar código del proyecto;
   distinguen dependencia faltante de error del código.
2. `main.DualSenseApp` compone conexión, perfiles, triggers, macros, audio,
   bandeja e interfaz y coordina el cierre.
3. `ConnectionManager` es propietario de `EmulatorManager` y concentra el
   estado de entrada del mando.
4. `src/emulator.py` es el escritor de la emulación ViGEm existente. Sus modos
   son Xbox 360 y DualShock 4, con arbitraje de fuentes, neutralización y
   feedback. Alpha 1 no lo importa ni lo cambia.
5. `ProfileManager`, `TriggerEngine`, `profile_catalog` y las páginas Qt
   conservan perfiles, configuración, migración y paquetes `.Nika`.
6. `gui.main_window.NikaidoWindow` administra páginas bajo demanda,
   suscripciones, timers y destrucción Qt. La base incluye regresiones de tres
   ciclos y Profile Studio.
7. `HidHideManager` separa detección y ayuda; no existe una ruta activa que
   instale un driver, cambie Secure Boot, HVCI o el BCD.

## Diagnóstico de viabilidad nativa

Microsoft define VHF como una interfaz para un driver fuente HID KMDF/WDM en
modo kernel que enlaza el WDK. UDE también se implementa como driver KMDF y
añade una pila USB emulada. Ninguna opción ofrece un dispositivo HID de sistema
seguro desde Python sin componente de kernel.

Un reporte estándar cubre botones, D-pad, sticks y gatillos. Ser identificado y
comportarse como DualSense exige además identidad válida y protocolos de
entrada, salida y funciones. Alpha 1 no usa VID/PID de Sony ni declara que su
reporte genérico sea el protocolo DualSense.

Windows moderno exige firma aceptada para drivers nuevos. Test signing modifica
la política de arranque y no es una vía de entrega; Secure Boot e Integridad de
memoria/HVCI deben permanecer habilitados. ViGEmBus, además de estar retirado,
expone Xbox 360 y DualShock 4, no DualSense. Por ello tampoco se reutiliza para
presentar una capacidad inexistente.

Fuentes primarias: [VHF de Microsoft](https://learn.microsoft.com/windows-hardware/drivers/hid/virtual-hid-framework--vhf-),
[muestra vhidmini2](https://github.com/microsoft/Windows-driver-samples/tree/main/hid/vhidmini2),
[arquitectura UDE](https://learn.microsoft.com/windows-hardware/drivers/usbcon/usb-emulated-device--ude--architecture),
[política de firma](https://learn.microsoft.com/windows-hardware/drivers/install/kernel-mode-code-signing-policy--windows-vista-and-later-),
[TESTSIGNING](https://learn.microsoft.com/windows-hardware/drivers/install/the-testsigning-boot-configuration-option),
[HVCI](https://learn.microsoft.com/windows-hardware/drivers/bringup/device-guard-and-credential-guard)
y [ViGEmBus](https://github.com/nefarius/ViGEmBus).

## Riesgos principales

- Un fallo de memoria o concurrencia en kernel puede bloquear o comprometer el
  sistema completo.
- Un driver no firmado o incompatible con HVCI puede no cargar y tentar una
  reducción insegura de protecciones.
- Una identidad VID/PID impropia puede crear problemas técnicos y legales.
- Dos backends escribiendo simultáneamente pueden duplicar entradas o dejar
  controles retenidos.
- Un protocolo incompleto puede fallar de forma distinta según juego,
  GameInput, anti-cheat o método de conexión.
- Un instalador sin reversión probada puede dejar servicios o dispositivos
  residuales.

El registro completo y sus controles están en `RISK_REGISTER_ALPHA1.md`.

## Plan Alpha 1 aplicado

1. Congelar y verificar la base oficial.
2. Auditar arquitectura, pruebas, imports, ciclo de vida, perfiles, launchers e
   instaladores sin modificarla.
3. Investigar VHF, UDE, firma, HVCI y el límite de ViGEm.
4. Definir un modelo de entrada estricto y un reporte HID genérico en memoria.
5. Implementar un contrato de backend y un simulador con neutralización, orden,
   concurrencia, fallos y cierre comprobables.
6. Crear una CLI diagnóstica independiente y de solo lectura.
7. Sellar el adaptador nativo hasta disponer de un entorno Windows seguro.
8. Añadir regresiones, validar el proyecto completo, auditar privacidad y crear
   un ZIP con manifiesto.

## Confirmación de aislamiento

- Cero archivos originales modificados o eliminados.
- Ningún módulo estable importa `virtual_dualsense_lab`.
- Configuración, perfiles y archivos `.Nika` no se leen ni se escriben por el
  laboratorio.
- No hay integración con PySide6 ni con la interfaz principal.
- No se importa `src.emulator`, `ConnectionManager`, ViGEm ni HidHide.
- No hay `.sys`, INF, CAT, instalador de driver ni elevación automática.
- No se ejecuta `bcdedit`, `pnputil`, `devcon` ni un shell externo.
- Secure Boot, test signing, HVCI y el BCD son de solo lectura o quedan fuera
  del entorno; nunca se modifican.

© Team Nikaido
