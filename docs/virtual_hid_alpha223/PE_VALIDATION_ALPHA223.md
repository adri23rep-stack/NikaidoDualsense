# Validación PE del driver — Alpha 2.2.3

## Cambio

Alpha 2.2.2 rechazaba cualquier SYS sin `IMAGE_FILE_SYSTEM`. La compilación real
con WDK demostró que esa condición no es válida como requisito universal. Alpha
2.2.3 conserva el campo como información, pero no decide con él.

## Condiciones obligatorias

El registro y el preparador exigen:

| Campo | Condición |
|---|---|
| Firma DOS | `MZ` |
| Firma PE | `PE\0\0` |
| Arquitectura | AMD64 |
| Formato opcional | PE32+ |
| Secciones | Una o más |
| Característica COFF | `IMAGE_FILE_EXECUTABLE_IMAGE` |
| Subsistema | Native |
| Punto de entrada | Distinto de cero |
| Certificado incrustado | Ausente |

`IMAGE_FILE_SYSTEM` puede estar presente o ausente. Ambas variantes pasan si
cumplen el resto.

## Por qué no se eliminó toda la barrera

La extensión `.sys` no demuestra que el archivo sea un driver. Las condiciones
anteriores siguen rechazando archivos dañados, ejecutables de usuario, imágenes
x86, archivos sin punto de entrada o binarios ya firmados de manera inesperada.

Después de esta barrera todavía se ejecutan:

1. comparación SHA-256 con las fuentes registradas;
2. validación del INF fuente;
3. `InfVerif /u`;
4. `Inf2Cat`;
5. comprobación de que el catálogo fue producido.

## Registro generado

`NikaidoVhfA223.build.json` usa esquema 2 e incluye un bloque sanitizado
`pe_validation`. Solo contiene propiedades técnicas del archivo, rutas
relativas, tamaños y hashes. No incluye usuario, hostname, ruta privada, fecha
o información del equipo.

## Límite

Pasar esta inspección no demuestra que Windows pueda cargar el driver. La carga
continúa bloqueada hasta contar con firma aceptada y una etapa separada de
validación en Windows.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
