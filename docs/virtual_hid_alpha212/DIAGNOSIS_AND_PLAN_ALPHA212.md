# Diagnóstico y plan — Alpha 2.1.2

## Diagnóstico corregido

La evidencia directa de Windows encontró `vhf.h` en las tres familias de WDK
instaladas:

- `Include\10.0.22621.0\shared\vhf.h`;
- `Include\10.0.26100.0\shared\vhf.h`;
- `Include\10.0.28000.0\shared\vhf.h`.

También confirmó un SDK y WDK 28000.1 instalados, junto con los headers,
bibliotecas, binarios e integración de Visual Studio correspondientes. Por lo
tanto, el entorno no requería otra reparación.

## Causa

Alpha 2.1.1 esperaba incorrectamente:

```text
Include\<versión>\km\vhf.h
```

La ubicación observada y correcta es:

```text
Include\<versión>\shared\vhf.h
```

El gate produjo un falso bloqueo 24 antes de ejecutar MSBuild. No existe aún
evidencia de que el driver compile o falle: el código C nunca fue evaluado en
esa ejecución.

## Corrección

1. Crear una copia independiente de Alpha 2.1.1.
2. Cambiar únicamente la ruta lógica de `vhf.h` de `km` a `shared`.
3. Mantener las otras seis comprobaciones sin cambios.
4. Añadir una regresión que reproduce la estructura real del WDK.
5. Añadir una regresión que impide volver a aceptar la ruta `km` errónea.
6. Conservar todos los launchers anteriores como wrappers compatibles.
7. No modificar, instalar ni reparar componentes de Windows.

## Riesgos de driver sin cambios

Que el gate pase solamente autoriza compilar el código fuente. No autoriza
instalar el `.sys`, no demuestra enumeración HID y no elimina los requisitos de
firma, Driver Verifier, HVCI y HLK.

## Aislamiento

La base estable 2.9.8.9 y Alpha 1, Alpha 2, Alpha 2.1 y Alpha 2.1.1 permanecen
intactas. No se modifican ViGEmBus, HidHide, Secure Boot, Integridad de memoria
o test signing.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
