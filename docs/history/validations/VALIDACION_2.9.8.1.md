# Validación Nikaido DualSense 2.9.8.1 Beta 1

## Alcance

Validación automatizada de Profile Studio 2.0, perfiles de fábrica, iconos vectoriales, presets de gatillos, compatibilidad de perfiles y cambios del Privacy Auditor.

## Resultado automatizado

- **461 pruebas aprobadas.**
- **2 pruebas omitidas** porque PySide6 no está instalado en el entorno de revisión.
- Compilación sintáctica completa mediante `compileall`: **aprobada**.
- Importación y serialización de perfiles: **aprobadas**.
- Compatibilidad del paquete `.Nika`: **aprobada**.
- Guardado de imagen, RGB, gatillos, vibración, macros, audio, mappings e Input Studio: **aprobado**.
- Protección de perfiles de fábrica y límite de perfiles personalizados: **aprobados**.
- Privacy Auditor 2.0 sobre el árbol fuente: **aprobado**.

## Regresiones cubiertas

- IDs históricos de perfiles conservados.
- Nuevos perfiles `racing` y `horror` disponibles.
- Iconos `theme:*` conservados al serializar y restaurar.
- Dashboard no muestra el token interno del tema como texto.
- Una sola fuente de tiempo anima todas las tarjetas de Profile Studio.
- Ninguna tarjeta crea su propio `QTimer`.
- El editor reutiliza la biblioteca de presets de Trigger Studio.
- Imágenes personalizadas mantienen prioridad sobre el avatar vectorial.
- Duplicado limpia recursos parciales si no puede registrarse el perfil.
- El Privacy Auditor no bloquea medios comprimidos por coincidencias aleatorias cortas, pero sí bloquea rutas privadas reales.

## Revisión manual pendiente en Windows

1. Abrir Profile Studio con escalado 100 %, 125 % y 150 %.
2. Revisar transición entre una, dos y tres columnas.
3. Crear, editar, clonar, marcar favorito, exportar, importar y eliminar un perfil.
4. Confirmar que Reducir movimiento disminuya las animaciones.
5. Aplicar los diez perfiles con un DualSense físico y comparar la sensación de L2/R2.
6. Probar Conducción precisa en un juego de carreras.
7. Probar Horror inmersivo y su efecto RGB tipo latido.
8. Compilar con Nuitka y generar el instalador protegido en Windows.

## Límites honestos

- No se conectó un DualSense físico durante esta revisión.
- No se ejecutó la interfaz Qt porque PySide6 no está instalado en el entorno.
- No se compiló el `.exe` ni el instalador de Windows.
