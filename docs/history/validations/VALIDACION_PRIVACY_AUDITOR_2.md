# Validación — Privacy Auditor 2.0

Fecha de validación: 2026-07-16

## Alcance

Se validó la nueva clasificación de privacidad y la integración con los builds
normal y protegido. No se generó un EXE de Windows dentro de este entorno Linux;
la compilación final con Nuitka debe repetirse en Windows usando
`COMPILAR_NIKAIDO_PROTEGIDO.bat`.

## Resultados automáticos

```text
python -m compileall -q main.py nikaido_version.py src gui tools build.py build_protected.py
Resultado: aprobado

pytest -q
Resultado: 442 aprobadas, 2 omitidas
```

Las dos pruebas omitidas necesitan PySide6, que no está instalado en este
entorno. Ninguna corresponde al motor de privacidad.

## Casos específicos aprobados

- Ruta de un compilador externo dentro de `qwindows.dll`: aviso, no bloqueo.
- Identidad del equipo actual dentro de una DLL: bloqueo.
- Ruta de usuario dentro de un JSON propio: bloqueo.
- Modo estricto de dependencias: bloqueo de metadatos externos.
- ZIP con DLL externa: aviso y ruta relativa.
- Reporte JSON: valores privados ocultos.
- Más de 80 avisos externos no pueden ocultar un error privado posterior.
- Comando Nuitka excluye pruebas y datos de `comtypes.test`.

## Prueba pendiente en Windows

1. Ejecutar `COMPILAR_NIKAIDO_PROTEGIDO.bat`.
2. Confirmar que los metadatos de Qt/Shiboken/ViGEm aparezcan como avisos.
3. Confirmar `BUILD PROTEGIDO EXITOSO Y VALIDADO`.
4. Abrir `release_protected/PRIVACY_AUDIT_PROTECTED.json`.
5. Confirmar que `blocking_findings` sea `0`.
6. Probar el EXE compilado, conexión del DualSense, RGB Studio, vibración,
   emulación y audio.

## Límites conocidos

- El auditor no elimina ni modifica DLL externas; solo clasifica sus cadenas.
- El modo estricto puede volver a bloquear dependencias legítimas.
- Un binario comprimido o cifrado puede contener datos no visibles mediante
  búsqueda directa de cadenas.
- La firma digital sigue pendiente y no forma parte de este hotfix.
