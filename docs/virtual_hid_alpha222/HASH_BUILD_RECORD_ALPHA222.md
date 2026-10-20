# Registro de compilación por hashes — Alpha 2.2.2

## Objetivo

Demostrar que el SYS preparado coincide con las fuentes presentes sin depender
de fechas de archivos.

## Ciclo

1. `BUILD_VHF_ALPHA222.bat` elimina el comprobante anterior mediante
   `clear-build-record`.
2. MSBuild reconstruye driver y cliente.
3. Si cualquiera falla, no existe un registro válido y el preparador bloquea.
4. Cuando ambos terminan bien, `record-build` valida el PE y el INF y escribe:

```text
native\vhf\driver\x64\Release\NikaidoVhfA222.build.json
```

5. `PREPARE_VHF_ALPHA222_PACKAGE.bat` vuelve a calcular todos los SHA-256 y
   exige coincidencia exacta antes de ejecutar herramientas del WDK.

## Contenido permitido

- Producto, publisher, versión y estado.
- Rutas relativas dentro del proyecto.
- Tamaños.
- SHA-256 del SYS y cuatro fuentes.
- Declaración de privacidad.

No contiene fecha, hora, usuario, hostname, ruta absoluta, información del
equipo, certificado o firma.

## Bloqueos

El preparador devuelve código 50 cuando:

- falta el registro;
- el JSON está dañado;
- pertenece a otra versión;
- faltan o sobran fuentes;
- una entrada está duplicada;
- cambió el contenido de una fuente;
- cambió el contenido del SYS.

El código 50 no indica que falte WDK ni solicita reinstalar componentes.

## Límites

El registro confirma coherencia local entre archivos, pero no demuestra firma,
instalación, carga, enumeración HID, estabilidad en kernel ni compatibilidad
con juegos. Es una barrera previa a `InfVerif` e `Inf2Cat`, no un reemplazo.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
