# Comprobación del cliente — Alpha 2.1.5

## Compilar

Desde Developer Command Prompt for VS 2026, en la raíz extraída:

```bat
CHECK_VHF_ALPHA215_ENVIRONMENT.bat
BUILD_VHF_ALPHA215.bat
```

Estos comandos no instalan, firman ni cargan el driver. La compilación debe
terminar con el driver y el cliente Release x64.

## Probar la ausencia de interfaz

Sin instalar el driver:

```bat
native\vhf\client\x64\Release\NikaidoVhfClient.exe status
echo Código de salida: %ERRORLEVEL%
```

Resultado normal:

```text
No se pudo abrir la interfaz Alpha 2.1.5 (error Win32 259). ...
Código de salida: 3
```

El número puede ser distinto si Windows devuelve otro fallo real, pero nunca
debe ser cero cuando el handle es inválido. Los acentos deben mostrarse sin
caracteres de reemplazo.

## Registrar hashes locales

```bat
certutil -hashfile native\vhf\driver\x64\Release\NikaidoVirtualHid.sys SHA256
certutil -hashfile native\vhf\client\x64\Release\NikaidoVhfClient.exe SHA256
```

Los hashes identifican los artefactos compilados; no demuestran firma,
instalación, enumeración HID ni compatibilidad con juegos.

## Seguridad

No ejecutes comandos de instalación y no cambies Secure Boot, Integridad de
memoria o test signing. El `.sys` local sigue sin catálogo y sin firma aceptada.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
