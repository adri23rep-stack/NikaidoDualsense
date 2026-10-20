# Validación Nikaido DualSense 2.9.8.5 Beta 1

## Resultado automatizado

- Suite completa: **483 pruebas aprobadas**.
- Pruebas omitidas: **2**, únicamente por ausencia de PySide6 en el entorno de revisión.
- Pruebas nuevas del hotfix de arranque: **5 aprobadas**.

## Cobertura específica

- El facade público importa el editor y la miniatura desde `gui/profile_editor.py`.
- `ProfilesPage` continúa perteneciendo a `gui/pages/profiles.py`.
- La ruta histórica `gui.pages.profiles.profile_image_widget` permanece disponible.
- Los exports públicos del editor se validan mediante AST sin depender de PySide6.
- El inicio seguro diferencia dependencias faltantes de errores del proyecto.
- El instalador no intenta reparar audio cuando el fallo pertenece al código de Nikaido.
- La arquitectura modular, el pipeline de compilación y la biblioteca de perfiles siguen cubiertos por sus pruebas anteriores.

## Validación técnica

- Compilación sintáctica: **159 archivos Python aprobados**.
- No se modificaron formatos de perfil ni estructuras persistentes del usuario.
- La versión se actualizó de manera consistente en aplicación, `pyproject`, metadatos e instaladores.
- Privacy Auditor del árbol fuente: **394 archivos revisados**, 0 bloqueos y 0 advertencias.
- Reporte: `docs/history/validations/PRIVACY_AUDIT_2.9.8.5.json`.
- Manifiesto de integridad: **393 archivos** con tamaño y SHA-256 individual.

## Límites

- PySide6 no está disponible en este entorno, por lo que dos pruebas Qt fueron omitidas.
- No se ejecutó la interfaz visual ni se compiló el instalador de Windows.
- No se realizó prueba física con un DualSense.
