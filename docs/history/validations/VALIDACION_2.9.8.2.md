# Validación Nikaido DualSense 2.9.8.2 Beta 1

## Resultado
- Suite automatizada completa: **463 pruebas aprobadas**.
- Pruebas omitidas: **2**, únicamente porque PySide6 no está instalado en este entorno.
- Compilación sintáctica: **152 archivos Python aprobados**.
- Regresión específica de claves de paleta en Profile Studio: aprobada.
- Privacy Auditor sobre el proyecto: aprobado, **368 archivos revisados**, 0 bloqueos y 0 advertencias.
- Manifiesto de integridad: **368 archivos** con SHA-256 individual.

## Falla corregida
Profile Studio usaba `C["violet"]`, pero la paleta oficial no contiene esa clave. El `KeyError` ocurría durante `refresh()` al construir las estadísticas y podía repetirse en el panel lateral. Se reemplazó por un color seguro basado en `accent2`, con fallback a `accent`.

## Prevención
- Nueva prueba automática que compara todas las claves `C[...]` de `gui/pages/profiles.py` contra la paleta real.
- El color secundario del perfil usa fallback seguro para que un cambio futuro en la paleta no vuelva a impedir abrir la pestaña.

## Límites
- No se realizó prueba física con un DualSense.
- No se compiló el instalador con Nuitka en Windows.
- Dos pruebas GUI que requieren PySide6 se omitieron por ausencia de la dependencia en este entorno.
