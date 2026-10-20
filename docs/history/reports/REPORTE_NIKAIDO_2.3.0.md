# Reporte técnico — Nikaido DualSense 2.3.0

## Objetivo

Realizar una pasada completa de calidad sobre Nikaido 2.2.0 sin volver a tocar innecesariamente las rutas HID, ViGEm y giroscopio que ya funcionan correctamente. La revisión se concentró en apariencia, Nikaido Nexus, rendimiento, guardado de datos, perfiles `.Nika`, arranque del ejecutable y facilidad de mantenimiento.

## 1. Nikaido Nexus

- Historial limitado de deshacer y rehacer.
- Copiar, pegar, duplicar, eliminar y reordenar acciones.
- Búsqueda por acción, destino, gesto o advertencia.
- Validación de macros, capas, perfiles y destinos faltantes.
- Crear, duplicar, renombrar, eliminar y marcar capas iniciales.
- Nexus Flow desplazable para configuraciones grandes.
- Visualización en vivo de botones físicos presionados.
- Navegación del DualSense visual con mouse, flechas y Enter.
- Atajos Ctrl+Z, Ctrl+Y, Ctrl+Shift+Z, Ctrl+C, Ctrl+V, Ctrl+D, Ctrl+F y Supr.
- Corrección del reordenamiento cuando la lista se encontraba filtrada.
- Límites defensivos de 32 capas, 16 acciones por entrada, ocho requisitos y 256 caracteres por destino.

Nexus continúa utilizando `AdvancedMapper`; no se creó un segundo motor de entrada.

## 2. Apariencia Studio

- Cinco presets: Nikaido, Cristal, Enfoque, AMOLED y Minimal.
- Cinco acentos: Violeta, Cian, Rosa, Verde y Ámbar.
- Modos de fondo cubrir, contener y estirar.
- Posición superior, centrada o inferior.
- Zoom real de 100 % a 180 %.
- Oscurecimiento y viñeta.
- Transparencia separada para paneles, sidebar y controles.
- Densidad cómoda o compacta.
- Reducción de movimiento.
- Barra lateral contraíble y persistente.
- Corrección del espacio del logo y botón al contraer el sidebar.
- El acento ahora se sincroniza con controles Qt y gráficos dibujados a mano.
- Vista previa con el logo real de Nikaido.
- Caché del fondo invalidada por ruta, fecha, tamaño, ventana, modo y zoom.
- Cambios de fondo sin reconstruir toda la hoja visual.

Las imágenes se verifican, orientan, reducen y escriben atómicamente en AppData. Se rechazan archivos falsos, gigantes o ilegibles.

## 3. Rendimiento y experiencia

- Dashboard cargado inmediatamente.
- Secciones pesadas creadas únicamente al abrirlas por primera vez.
- Temporizador de interfaz adaptado a páginas en vivo o estáticas.
- Fallos de construcción aislados por sección, con reintento y acceso al diagnóstico.
- Paleta global Ctrl+K con navegación, perfiles, conexión, guardado, gyro y temas.
- Indicador de cambios pendientes, guardado correcto o error de escritura.
- Animaciones más cortas y compatibles con reducción de movimiento.
- Se eliminó trabajo repetido al validar acciones de Nexus.

## 4. Perfiles y formato `.Nika`

- Importación transaccional: un fallo no deja datos instalados parcialmente.
- Límite de 25 MB por paquete, diez MB por miembro y 32 miembros.
- Límites de macros y efectos incluidos.
- Rechazo de paquetes cifrados y nombres duplicados.
- Imágenes verificadas por contenido real, no únicamente por extensión.
- IDs de macros remapeados dentro de acciones de Nexus al importar.
- Referencias al mismo perfil remapeadas al nuevo ID.
- Exportación automática de macros utilizadas por Nexus.
- Exportación segura de perfiles antiguos con imágenes inválidas.
- La configuración conserva campos desconocidos para futuras migraciones.

Se mantiene:

- `CONFIG_VERSION = 2.0.0`
- `NIKA_FORMAT_VERSION = 1`

## 5. Guardado y recuperación

- Escritura JSON temporal con `flush`, `fsync` y reemplazo atómico.
- Reintentos breves para bloqueos de antivirus, indexadores o sincronizadores.
- Respaldos limitados y restauración del último JSON válido.
- Limpieza opcional de miniaturas y fondos huérfanos al restablecer.
- Estado de guardado visible en la interfaz.

## 6. Estabilidad del ejecutable

- Protección contra dos instancias usando mutex de Windows correctamente tipado para 64 bits.
- Reportes locales limitados para fallos del hilo principal y workers.
- Errores fatales visibles aun cuando el EXE se compila sin consola.
- Cierre idempotente de módulos después de inicio completo o parcial.
- Un fallo de Qt en el EXE ya no cae en una consola invisible esperando `input()`.
- Las pantallas opcionales no pueden derribar la conexión principal si fallan al abrir.

## 7. Compilación y distribución

El compilador ahora genera y verifica:

- metadatos de versión de Windows;
- icono y recursos;
- runtime de Python;
- extensión HID nativa;
- importación de pydualsense;
- enumeración HID dentro del EXE;
- plugin `qwindows.dll`;
- manifiesto de distribución con SHA-256 del ejecutable;
- carpeta `release` y lanzador inequívoco.

Las instrucciones del README ya no apuntan a `build` o `dist`, sino a `release\\Nikaido\\Nikaido.exe`.

## 8. Arquitectura nueva

- `src/appearance.py`: normalización, presets y firmas de cambios sin depender de Qt.
- `src/edit_history.py`: historial reutilizable y limitado.
- `src/single_instance.py`: exclusión mutua multiplataforma.
- `src/crash_reporting.py`: reportes locales y avisos fatales visibles.

La lógica permanece separada de la interfaz para facilitar pruebas y mantenimiento.

## 9. Validación

- **170 pruebas automatizadas aprobadas.**
- Todos los archivos Python pasan `compileall`.
- No se detectaron métodos duplicados en clases.
- Se comprobó la generación del manifiesto y SHA-256 mediante pruebas.
- El paquete final se entrega sin `__pycache__`, `.pyc`, `.pytest_cache`, `.coverage`, compilaciones ni temporales.

## Limitación del entorno

Este entorno no dispone de Windows, PySide6, ViGEm ni un DualSense físico. Por eso no fue posible abrir visualmente la interfaz ni hacer la prueba final USB/Bluetooth del ejecutable. La ruta HID, el passthrough DS4, el orden de la IMU y la emulación no se modificaron en esta versión; la validación física final debe realizarse al compilar en Windows.
