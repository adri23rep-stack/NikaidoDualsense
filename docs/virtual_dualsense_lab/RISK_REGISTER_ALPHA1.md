# Registro de riesgos — Virtual DualSense Lab Alpha 1

| ID | Riesgo | Nivel | Control aplicado en Alpha 1 | Estado |
| --- | --- | --- | --- | --- |
| VDL-01 | Crash o vulnerabilidad en kernel | Crítico | No se incluye código ni binario de driver | Mitigado para Alpha 1 |
| VDL-02 | Driver sin firma o incompatible con HVCI | Crítico | Backend nativo sellado; no hay instalación | Mitigado para Alpha 1 |
| VDL-03 | Debilitar Secure Boot/test signing | Crítico | Política explícita de cero modificaciones | Mitigado |
| VDL-04 | Suplantar identidad VID/PID | Alto | Descriptor genérico sin identidad Sony | Mitigado |
| VDL-05 | Doble escritor con ViGEm estable | Alto | Paquete y punto de entrada independientes | Mitigado |
| VDL-06 | Botones o ejes retenidos al cerrar | Alto | Neutralización obligatoria e idempotente | Cubierto por pruebas |
| VDL-07 | Estados fuera de orden | Alto | Secuencia estrictamente creciente | Cubierto por pruebas |
| VDL-08 | Valores NaN, infinitos o fuera de rango | Alto | Modelo inmutable y validación estricta | Cubierto por pruebas |
| VDL-09 | Condiciones de carrera | Medio | Locks reentrantes y orquestador serializado | Cubierto por pruebas |
| VDL-10 | Historial sin límite | Medio | `deque` con límite validado | Cubierto por pruebas |
| VDL-11 | Callback defectuoso rompe el motor | Medio | Aislamiento y retiro del callback fallido | Cubierto por pruebas |
| VDL-12 | Diagnóstico filtra datos personales | Alto | Sin usuario, hostname, rutas ni IDs de dispositivo | Cubierto por pruebas |
| VDL-13 | Juego interpreta el dispositivo de forma distinta | Alto | No se publica dispositivo; requiere pruebas Windows futuras | Pendiente futuro |
| VDL-14 | Reacción de anti-cheat o DRM | Alto | No se prueba ni se promete compatibilidad | Pendiente futuro |
| VDL-15 | Protocolo DualSense incompleto | Alto | Se declara reporte genérico, no DualSense real | Aceptado en Alpha 1 |

Ningún riesgo pendiente autoriza instalar un driver ni reducir protecciones del
sistema. Esos pasos requieren una fase y una aprobación técnica separadas.

