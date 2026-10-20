# Reporte de arquitectura — Nikaido DualSense 2.6.0

**Base usada:** Nikaido 2.5.6 Security Hardening  
**Objetivo:** dividir la interfaz monolítica sin cambiar comportamiento.

## Resultado

La migración quedó completada como una versión de arquitectura. El antiguo
`gui/modern_app.py` tenía **10,984 líneas** y concentraba la ventana, widgets,
diálogos y todas las páginas. Ahora tiene **32 líneas** y funciona como fachada
pública compatible.

La implementación quedó distribuida así:

| Archivo | Responsabilidad | Líneas aproximadas |
|---|---|---:|
| `gui/main_window.py` | Ventana, navegación, estado y coordinación | 1,171 |
| `gui/components.py` | Widgets y componentes reutilizables | 1,012 |
| `gui/pages/dashboard.py` | Dashboard | 367 |
| `gui/pages/profiles.py` | Perfiles y editor | 710 |
| `gui/pages/nexus.py` | Nexus y mapper | 1,635 |
| `gui/pages/input.py` | Input Studio, calibración y gyro | 1,074 |
| `gui/pages/macros.py` | Biblioteca y editor de macros | 1,555 |
| `gui/pages/device.py` | Luces, vibración, gatillos y audio | 1,106 |
| `gui/pages/system.py` | Automatización, compatibilidad, diagnóstico, emulación y herramientas | 1,798 |
| `gui/pages/settings.py` | Wizard y ajustes | 962 |

## Compatibilidad

- `main.py` sigue importando `DualSenseGUI` desde `gui.modern_app`.
- `gui.app` continúa funcionando.
- Las clases históricas siguen reexportadas desde `gui.modern_app`.
- No cambió el formato `.Nika`, la configuración ni las rutas de AppData.
- PyInstaller incluye explícitamente los 13 módulos Qt necesarios.

## Prueba de equivalencia

Se comparó el AST de las **43 definiciones superiores** del archivo 2.5.6 con
las definiciones extraídas en 2.6.0:

- Definiciones faltantes: **0**
- Definiciones duplicadas: **0**
- Definiciones con lógica modificada: **0**

Esta comparación incluye páginas, widgets, diálogos, `NikaidoWindow` y
`DualSenseGUI`. Los cambios de versión, documentación, build y pruebas quedan
fuera de esa equivalencia porque son parte intencional de la entrega.

## Pruebas añadidas

La suite ahora revisa que:

- `modern_app.py` siga siendo una fachada pequeña.
- Las páginas no regresen al archivo monolítico.
- No existan clases superiores duplicadas.
- Los módulos permanezcan dentro de límites revisables.
- Ningún módulo de implementación importe la fachada de vuelta.
- PyInstaller recopile toda la interfaz modular.
- La versión coincida entre Python, `pyproject.toml` e Inno Setup.
- Las pruebas históricas inspeccionen toda la interfaz modular sin importar Qt.

## Validación realizada

- **270 pruebas aprobadas**.
- `compileall` correcto para `main.py`, `src`, `gui` y `tests`.
- Ruff crítico (`E9`, `F63`, `F7`, `F82`) sin errores.
- Bandit con nivel medio/alto: sin hallazgos.
- Import completo de `gui.modern_app` con un entorno Qt simulado: correcto.
- Reexportaciones públicas encontradas: **43**.
- Comparación AST contra 2.5.6: **43 de 43 idénticas**.

## Validación pendiente

Este entorno no contiene PySide6 ni escritorio Windows real. Antes de declarar
la versión pública final se recomienda abrirla en Windows y recorrer Dashboard,
Perfiles, Nexus, Macros, Emulación, Compatibilidad, Ajustes y el wizard. También
conviene probar cierre, bandeja y un juego con el DualSense conectado.

No se detectó un cambio funcional en código, pero esa prueba física sigue
siendo necesaria para detectar problemas propios de Qt, PyInstaller o Windows.
