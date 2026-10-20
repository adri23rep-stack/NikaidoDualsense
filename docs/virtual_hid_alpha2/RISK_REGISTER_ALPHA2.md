# Registro de riesgos — Virtual HID Enumeration Prototype Alpha 2

| ID | Riesgo | Nivel | Control Alpha 2 | Estado |
| --- | --- | --- | --- | --- |
| VHE-01 | Crash o corrupción en kernel | Crítico | Solo fuente; revisión y WDK pendientes | Bloquea instalación |
| VHE-02 | Driver sin firma | Crítico | No se incluye binario, CAT o instalador | Bloqueado |
| VHE-03 | Debilitar protecciones | Crítico | Sin test signing, BCD o cambios de HVCI/Secure Boot | Mitigado |
| VHE-04 | Suplantar VID/PID | Alto | Ambos valores permanecen en cero | Mitigado |
| VHE-05 | Escritura por procesos no autorizados | Alto | ACL SYSTEM/administradores | Mitigado provisional |
| VHE-06 | Dos clientes escribiendo | Alto | Dispositivo exclusivo | Mitigado |
| VHE-07 | Botones retenidos al morir el cliente | Alto | Cleanup y watchdog de 500 ms | Implementado, no probado en kernel |
| VHE-08 | Estado retenido en suspensión | Alto | Neutralización D0Entry/D0Exit | Implementado, no probado en kernel |
| VHE-09 | Buffer o versión inválidos | Alto | Estructuras empacadas, tamaño fijo y versión | Cubierto estáticamente |
| VHE-10 | Reportes fuera de orden | Medio | Secuencia de 64 bits creciente | Cubierto estáticamente |
| VHE-11 | Descriptor distinto al simulador | Medio | Comparación byte por byte en pytest | Cubierto |
| VHE-12 | Juego no reconoce HID genérico | Alto | Se declara limitación; pruebas futuras | Pendiente |
| VHE-13 | Anti-cheat rechaza el driver | Alto | No se promete compatibilidad | Pendiente |
| VHE-14 | INF incorrecto o no universal | Alto | InfVerif/WDK obligatorios antes de uso | Pendiente |
| VHE-15 | Compilación confundida con entrega | Alto | Firma e Inf2Cat desactivados; mensajes explícitos | Mitigado |

El código fuente no reduce el nivel de riesgo de una ejecución en kernel. Por
eso ningún punto “implementado” equivale a una prueba Windows aprobada.

© Team Nikaido

