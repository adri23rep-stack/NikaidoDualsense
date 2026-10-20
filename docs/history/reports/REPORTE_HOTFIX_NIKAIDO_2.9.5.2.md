# Reporte de hotfix — Nikaido DualSense 2.9.5.2

## Error recibido

Pip mostraba todas las versiones publicadas de pycaw, incluida `20251023`, pero terminaba con:

```text
ERROR: Could not find a version that satisfies the requirement pycaw<2027,>=20251023
```

## Causa exacta

El archivo `requirements-runtime.txt` contenía:

```text
pycaw>=20251023,<2027
```

Pycaw utiliza números de versión basados en fecha. Por tanto, `20251023` es numéricamente mayor que `2027`. El requisito exigía simultáneamente una versión mayor o igual a 20251023 y menor que 2027, algo imposible.

El problema no era la instalación parcial, `comtypes`, el micrófono ni Python 3.10.

## Reparación

El requisito quedó fijado a la versión para la que fue escrito el adaptador de Core Audio:

```text
pycaw==20251023; platform_system == "Windows"
```

Se conserva:

```text
comtypes>=1.4.10,<2; platform_system == "Windows"
```

También se añadieron pruebas que:

- comprueban que `20251023` satisface el requisito de pycaw;
- detectan rangos contradictorios entre mínimos y máximos;
- verifican que pycaw solo se instala en Windows;
- aseguran que `install.bat` y el reparador usan la misma fuente de dependencias.

## Uso recomendado

Extraer la 2.9.5.2 en una carpeta nueva y ejecutar `install.bat`. Si se copia encima de una carpeta que ya tiene `.venv`, puede ejecutarse `REPARAR_GUI_Y_AUDIO.bat`; el entorno parcial puede reutilizarse.

## Validación

- 385 pruebas aprobadas y una omitida por falta de PySide6 en Linux.
- 4 pruebas específicas de resolución de dependencias aprobadas.
- Compilación Python y Ruff aprobados.
- Auto-pruebas portables principales aprobadas.
- Bandit sin problemas medios o graves.

La validación física de Core Audio, el botón MIC y el LED requiere Windows y un DualSense real.
