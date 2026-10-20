# Hotfix de runtime ViGEm — Nikaido 2.9.2

La primera salida standalone protegida compiló los módulos Python de `vgamepad`,
pero Nuitka no copió el archivo nativo que ese paquete carga mediante `ctypes`:

`vgamepad/win/vigem/client/x64/ViGEmClient.dll`

El resultado era un error al inicializar `src.emulator` antes de abrir la GUI.

## Solución

- El pipeline copia explícitamente el árbol nativo `win/vigem/client` desde el
  paquete `vgamepad` instalado en el entorno protegido.
- La validación falla antes de publicar si falta la DLL x64.
- `REPARAR_RUNTIME_PROTEGIDO.bat` actualiza una compilación standalone ya
  existente sin volver a ejecutar Nuitka.
- Después de reparar, se regenera el manifiesto y el ZIP protegido.

## Flujo rápido

1. Copiar los archivos del parche dentro del proyecto ya compilado.
2. Ejecutar `REPARAR_RUNTIME_PROTEGIDO.bat`.
3. Probar `release_protected/Nikaido/Nikaido.exe`.
4. Ejecutar `CREAR_INSTALADOR_PROTEGIDO.bat` y reinstalar.
