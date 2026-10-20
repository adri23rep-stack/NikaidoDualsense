# Validación Nikaido DualSense 2.9.8.4 Beta 1

## Resultado automatizado

- Suite completa: **478 pruebas aprobadas**.
- Pruebas omitidas: **2**, únicamente por ausencia de PySide6 en el entorno de revisión.
- Pruebas específicas nuevas de la galería: **9 aprobadas**.

## Cobertura específica

- Exactamente ocho perfiles incluidos y orden estable.
- Nombres, categorías, tags y presentación diferenciada.
- Gatillos, RGB, vibración e Input Studio propios por perfil.
- Aliases históricos compatibles sin tarjetas duplicadas.
- Migración de perfil activo, favoritos, reglas por juego y macros.
- Preservación de imagen personal, Input Studio, mapeo avanzado y audio.
- Restauración segura de perfiles incluidos.
- Sanitización de overrides malformados.
- Roundtrip de metadatos para perfiles personales e importados.
- Ocho portadas PNG originales, decodificables y con dimensiones controladas.
- Generador de arte sin red ni carga de imágenes externas.
- Galería sin temporizadores continuos.
- Módulos nuevos incluidos en el pipeline de compilación.

## Validación técnica

- Compilación sintáctica: **158 archivos Python aprobados**.
- Privacy Auditor del árbol fuente: **390 archivos revisados**, 0 bloqueos y 0 advertencias.
- Reporte: `docs/history/validations/PRIVACY_AUDIT_2.9.8.4.json`.
- Manifiesto de integridad: **389 archivos** con tamaño y SHA-256 individual.
- Privacy Auditor del ZIP final: 1 archivo contenedor y 1 archivo comprimido revisados, 0 bloqueos y 0 advertencias.
- El ZIP final se verifica sin `__pycache__`, `.pytest_cache`, `.pyc` ni `.pyo`.

## Límites

- No se realizó prueba física con un DualSense.
- No se ejecutó la interfaz Qt porque PySide6 no está disponible en este entorno.
- No se compiló Nuitka ni el instalador de Windows.
