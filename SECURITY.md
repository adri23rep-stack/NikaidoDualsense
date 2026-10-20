# Seguridad de Nikaido DualSense

## Versión con soporte

La rama mantenida es **2.6.1 o posterior**. Los perfiles `.Nika` y temas creados
por terceros deben tratarse como archivos no confiables, aunque parezcan venir
de una comunidad conocida.

## Reportar un problema

No publiques una vulnerabilidad con pasos de explotación en un issue abierto.
Comparte de forma privada la versión afectada, impacto y una forma mínima de
reproducirla. No adjuntes perfiles personales, macros privadas, reportes
completos ni rutas de usuario sin revisarlos primero.

## Modelo de seguridad

- Nikaido no necesita ejecutarse como administrador para su uso normal.
- ViGEmBus e HidHide son componentes externos y deben obtenerse desde sus
  canales oficiales.
- Los paquetes `.Nika` y `.nikaido-theme` se validan por tamaño, estructura,
  rutas, nombres de Windows, compresión, JSON e imágenes antes de usarlos.
- Nikaido no ejecuta código incluido dentro de perfiles o temas.
- Los reportes de diagnóstico se guardan localmente y no se envían solos.
- La reparación Bluetooth conserva emparejamientos ajenos al DualSense.
- Los lanzamientos todavía no están firmados digitalmente; verifica el SHA-256
  publicado antes de distribuirlos.

## Comprobaciones del proyecto

```powershell
python -m compileall -q main.py nikaido_version.py src gui
python -m pytest -q
python -m ruff check --select E9,F63,F7,F82,F841 main.py src gui tests
python -m bandit -r main.py src gui -ll
python -m pip_audit -r requirements-runtime.txt
```

Las distribuciones compiladas incluyen `MANIFEST.json` con ruta, tamaño y
SHA-256 de cada archivo. `pip-audit` requiere acceso a Internet y se ejecuta en
el flujo de CI para Windows.
## Auditoría de privacidad de releases

El build normal y el protegido usan Privacy Auditor 2.0 antes de empaquetar.
Los términos del entorno actual y `NIKAIDO_PRIVACY_TERMS` bloquean en cualquier
archivo. Las rutas de compiladores externos encontradas dentro de DLL/PYD/EXE
se registran como avisos, pero no se confunden con datos del equipo actual. Los
reportes distribuidos usan rutas relativas y valores ocultos. Consulta
`docs/PRIVACY_AUDITOR_2.md`.

