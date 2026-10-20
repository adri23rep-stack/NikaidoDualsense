# Validación Nikaido DualSense 2.9.8.6 Beta 1

## Resultado automatizado

- Suite completa: **490 pruebas aprobadas**.
- Pruebas omitidas: **0**.
- Pruebas nuevas del hotfix de editor: **5 aprobadas**.
- PySide6 usado para validación Qt: **6.8.3**.
- Plataforma Qt de pruebas: `offscreen`.

## Cobertura específica

- El editor importa el helper `label` que utiliza durante su construcción.
- Los ocho perfiles incluidos pueden abrirse, modificarse y aceptarse en un diálogo Qt real.
- **Nuevo perfil** funciona sin un perfil aplicado y usa el perfil seleccionado o el predeterminado como fuente.
- El botón superior de creación completa el flujo y registra el perfil personalizado.
- El botón lateral **Editar perfil** completa el flujo y guarda cambios.
- Se conservan los mensajes de confirmación y la persistencia de perfiles personalizados y overrides.
- Las filas del panel de detalle usan una hoja de estilo Qt válida, sin la llave duplicada que provocaba advertencias de parseo.
- Las rutas de imágenes y configuraciones de Input Studio mantienen su limpieza en caso de fallo.

## Validación técnica

- Compilación sintáctica: **160 archivos Python aprobados**.
- No se modificó el formato de perfiles ni de configuración persistente.
- La versión se actualizó en aplicación, `pyproject`, metadatos e instaladores.
- Privacy Auditor y manifiesto de integridad se regeneran durante el cierre de la release.

## Límites

- No se realizó prueba física con DualSense.
- No se ejecutó la interfaz sobre Windows ni se compiló el instalador.
- La validación visual se limitó al backend gráfico `offscreen`; los flujos y widgets sí se construyeron con PySide6 real.
