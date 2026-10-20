# Diagnóstico y plan — Alpha 2.1.1

> **Corrección posterior:** la evidencia de Windows recibida después de esta
> entrega demostró que `vhf.h` sí estaba instalado en la carpeta `shared` del
> WDK 28000. Alpha 2.1.1 lo buscaba incorrectamente en `km`. Las conclusiones
> sobre un WDK incompleto quedan sustituidas por Alpha 2.1.2.

## Evidencia recibida de Windows

La comprobación de Alpha 2.1 detectó correctamente MSBuild 18.8.2, Visual
Studio 2026, `v145`, la integración `WindowsKernelModeDriver10.0` y las
bibliotecas Spectre x64. El gate detuvo la compilación antes de ejecutar
MSBuild porque no encontró un kit 28000 completo.

Las comprobaciones manuales posteriores identificaron el estado real del kit
`10.0.28000.0`:

| Componente | Estado observado |
| --- | --- |
| `ntddk.h` | Presente |
| `vhf.h` | Ausente |
| `guiddef.h` | Presente |
| `VhfKm.lib` | Presente |
| `SetupAPI.lib` | Presente |
| Props de driver de kernel | Presentes |

Después de reparar el entorno, Alpha 2.1 siguió bloqueando. No existe evidencia
de un error del driver: la compilación se canceló durante la comprobación de
dependencias y el header obligatorio `vhf.h` continuó ausente.

## Causas

1. El paquete local del WDK 28000 está incompleto para VHF: contiene
   `VhfKm.lib`, pero no el header correspondiente.
2. La integración de WDK dentro de Visual Studio y el contenido independiente
   del WDK son comprobaciones distintas. Reparar la integración no garantiza
   que se restaure un header del paquete independiente.
3. Alpha 2.1 agrupaba siete archivos en un único estado. El bloqueo era seguro,
   pero su mensaje podía inducir a repetir una reparación general innecesaria.

## Riesgos y decisiones

| Riesgo | Decisión Alpha 2.1.1 |
| --- | --- |
| Copiar `vhf.h` desde el kit 26100 | Prohibido; no se mezclan kits |
| Omitir el gate para forzar MSBuild | Prohibido; conserva el bloqueo 24 |
| Confundir VSIX con contenido del WDK | Se muestran estados separados |
| Publicar rutas o datos del equipo | El informe solo conserva nombres lógicos y versiones |
| Instalar un `.sys` no firmado | Sigue sin existir comando de instalación |
| Cambiar protecciones de Windows | Sigue prohibido por diseño |

## Plan ejecutado

1. Crear una copia independiente de Alpha 2.1.
2. Mantener intactos el driver, descriptor, protocolo y simulador.
3. Enumerar cada componente del SDK/WDK bajo una misma raíz y versión.
4. Evitar combinar headers y bibliotecas encontrados en raíces distintas.
5. Mostrar el componente exacto ausente en texto y JSON sanitizado.
6. Conservar comandos anteriores como wrappers compatibles.
7. Añadir regresiones para `vhf.h` ausente, privacidad y raíces separadas.
8. Ejecutar pruebas, sintaxis, lint, privacidad y empaquetado limpio.

## Aislamiento

Alpha 2.1.1 no modifica la base estable 2.9.8.9 ni las entregas Alpha 1,
Alpha 2 o Alpha 2.1. No se integra en PySide6, el instalador principal,
ViGEmBus o HidHide. No instala, firma, carga ni enumera un driver.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
