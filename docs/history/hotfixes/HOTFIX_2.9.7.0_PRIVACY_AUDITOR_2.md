# Hotfix 2.9.7.0 — Privacy Auditor 2.0

## Motivo

La compilación protegida terminaba correctamente en Nuitka, pero la validación
posterior rechazaba DLL legítimas de Qt, Shiboken y ViGEm por rutas históricas
como `C:\Users\<compilador-externo>`. El fallo ocurría después de generar el EXE
y obligaba a recompilar sin que existiera una filtración del equipo de Team
Nikaido.

## Cambios

- La auditoría distingue datos del entorno actual de metadatos externos.
- Los términos privados del equipo continúan bloqueando en cualquier archivo.
- Las rutas desconocidas dentro de archivos propios siguen bloqueando.
- Las rutas históricas en DLL/PYD/EXE pasan a aviso informativo.
- Las rutas de salida mostradas por el auditor son relativas.
- Los reportes JSON ocultan los valores privados.
- Se agregó modo estricto opcional para revisar dependencias externas.
- Nuitka deja fuera `comtypes.test`, sus datos de prueba y dependencias de pruebas como `unittest`; los imports de `doctest` desaparecen al excluir esos módulos de prueba.
- El build normal y protegido incluyen un comprobante de auditoría en su ZIP.

## Compatibilidad

No cambia perfiles, controles, RGB Studio, vibración, gatillos, macros, audio,
HidHide, ViGEm ni el formato `.Nika`. Solo cambia la etapa de compilación y
validación de privacidad.

## Pruebas añadidas

- DLL externa con ruta de otro compilador: aviso, no error.
- DLL externa con identidad del equipo actual: error.
- Archivo propio con ruta de usuario: error.
- Modo estricto: bloquea metadatos externos.
- ZIP con DLL externa: clasificación correcta y etiquetas relativas.
- Reporte JSON: valores y rutas absolutas ocultos.
- Comando Nuitka: exclusión de pruebas de `comtypes`.

## Hotfix 2.0.1 — compatibilidad con Nuitka

Se retiró la opción inexistente `--noinclude-doctest-mode=nofollow`, que hacía
que Nuitka cancelara antes de compilar. `doctest` no dispone de un modo
anti-bloat independiente en Nuitka; su inclusión se evita excluyendo
`comtypes.test` y sus archivos de prueba.

Validación del hotfix:

- 442 pruebas aprobadas.
- 2 pruebas omitidas por falta de PySide6 en el entorno de validación.
- Compilación sintáctica completa aprobada.
- No se realizó compilación Nuitka de Windows ni prueba física del instalador
  desde este entorno.
