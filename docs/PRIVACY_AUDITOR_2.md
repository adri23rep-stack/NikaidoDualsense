# Privacy Auditor 2.0

Nikaido DualSense revisa cada distribución antes de crear el ZIP final. El
objetivo es impedir que nombres, rutas privadas, usuarios de Windows, nombres
del equipo o términos definidos por Team Nikaido se filtren en una release.

## Qué cambió

La primera versión trataba cualquier cadena `C:\Users\ExampleUser\...` como un error. Eso
producía falsos positivos porque varias DLL externas de Qt, Shiboken y ViGEm
conservan rutas históricas del equipo donde sus autores compilaron esas
bibliotecas.

Privacy Auditor 2.0 separa los hallazgos en tres grupos:

1. **Datos del equipo actual — bloquean.**
   Se obtienen en tiempo de compilación desde `USERNAME`, `USERPROFILE`, `HOME`,
   `USER`, `COMPUTERNAME` y `NIKAIDO_PRIVACY_TERMS`.
2. **Rutas dentro de archivos propios — bloquean.**
   Un JSON, TXT, BAT, XML, manifiesto u otro archivo distribuido por Nikaido no
   debe contener rutas de usuario, aunque el nombre no coincida con el equipo
   actual.
3. **Metadatos históricos en binarios nativos — aviso.**
   Rutas de compiladores externos dentro de DLL, PYD o EXE se registran, pero no
   detienen la release mientras no coincidan con el entorno actual.

Los términos privados explícitos siempre bloquean, incluso dentro de una DLL de
terceros.

## Reporte seguro

Cada build normal genera `PRIVACY_AUDIT.json` y cada build protegido genera
`PRIVACY_AUDIT_PROTECTED.json`. Los reportes:

- usan rutas relativas;
- ocultan los valores detectados;
- muestran cuántos archivos se revisaron;
- separan errores y avisos;
- pueden incluirse en el ZIP sin revelar la ruta local del compilador.

## Variables opcionales

### Términos adicionales

```bat
set NIKAIDO_PRIVACY_TERMS=identificador-interno;nombre-interno;carpeta-secreta
```

### Modo estricto para dependencias

```bat
set NIKAIDO_PRIVACY_STRICT_THIRD_PARTY=1
```

En modo estricto, las rutas históricas encontradas dentro de DLL externas vuelven
a tratarse como errores. No se recomienda para releases normales porque puede
bloquear Qt, Shiboken o ViGEm sin que exista una filtración del equipo actual.

### Mostrar el valor privado localmente

```bat
set NIKAIDO_PRIVACY_SHOW_VALUES=1
```

Por defecto, el error oculta el valor privado incluso en consola. Esta opción
solo debe usarse localmente para localizar una cadena difícil de limpiar.

## Uso manual

```powershell
python tools/privacy_audit.py release_protected\Nikaido --json-report privacy.json
```

El comando devuelve código `0` cuando no existen errores atribuibles al equipo
de compilación. Los avisos de metadatos externos no cambian ese resultado.

## Reducción de ruido en Nuitka

El build protegido excluye `comtypes.test`, sus datos de prueba y las cargas de
`unittest`/`doctest`. Esto reduce archivos innecesarios y evita advertencias de
anti-bloat sin quitar los módulos de COM usados por Pycaw.
