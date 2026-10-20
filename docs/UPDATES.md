# Publicar actualizaciones de Nikaido

Nikaido 2.9.7.0 incluye el motor de actualización, pero la URL pública está vacía hasta alojar el instalador y el manifiesto oficial.

## Compilar el instalador y el manifiesto

En Windows, define la dirección donde quedarán los instaladores y compila:

```bat
set NIKAIDO_UPDATE_DOWNLOAD_BASE_URL=https://tu-dominio.example/releases
python build.py --installer
```

La carpeta `release` contendrá:

- `Nikaido_DualSense-2.9.7.0-Setup.exe`
- `Nikaido-update-manifest.json`

El manifiesto ya incluye tamaño y SHA-256 reales. Antes de publicarlo, reemplaza las notas provisionales por las notas definitivas.

## Configurar la aplicación

Cuando exista una dirección fija para el manifiesto, colócala en `UPDATE_MANIFEST_URL` dentro de `nikaido_version.py` antes de compilar la release pública. Durante pruebas internas también puede usarse:

```bat
set NIKAIDO_UPDATE_MANIFEST_URL=https://tu-dominio.example/releases/Nikaido-update-manifest.json
```

## Reglas de publicación

1. Publica primero el instalador.
2. Comprueba que su tamaño y SHA-256 coincidan con el manifiesto.
3. Publica el manifiesto al final.
4. Nunca reutilices una versión con archivos diferentes.
5. Conserva el mismo `AppId` del instalador para actualizar sobre la instalación existente.
6. La edición de Steam debe iniciar con `NIKAIDO_DISTRIBUTION=steam`; en ese modo el actualizador interno se desactiva.
