# Compuerta VS2026/WDK — Alpha 2.1.2

Desde **Developer Command Prompt for VS 2026**:

```bat
CHECK_VHF_ALPHA212_ENVIRONMENT.bat
```

En un entorno equivalente al observado en Windows, los siete componentes deben
aparecer como `OK`, incluido:

```text
[OK   ] vhf.h
```

Después, y solamente si aparece `[LISTO] Toolchain compatible para compilar
fuente`, puede ejecutarse:

```bat
BUILD_VHF_ALPHA212.bat
```

El script compila primero el proyecto KMDF/VHF y después el cliente C++. No
instala, firma, carga o ejecuta el driver. Si MSBuild falla después de pasar el
gate, el resultado debe tratarse como un error de código o proyecto y revisarse
desde el primer mensaje del compilador.

Producto: Nikaido DualSense  
Publisher: Team Nikaido  
Copyright: © Team Nikaido
