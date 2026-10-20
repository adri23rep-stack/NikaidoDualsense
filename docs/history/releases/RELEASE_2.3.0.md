# Nikaido DualSense 2.3.0

La 2.3.0 no busca inflar Nikaido con funciones aisladas. Es una revisión completa de calidad, rendimiento, seguridad de datos y experiencia de uso sobre la base 2.2.

## Nikaido Nexus

- Historial real de **deshacer y rehacer**, limitado para no crecer sin control.
- Copiar, pegar, duplicar, eliminar y reordenar acciones.
- Búsqueda por acción, destino, gesto o advertencia.
- Validación de macros, capas, perfiles y valores que ya no existen.
- Administración completa de capas: crear, duplicar, renombrar, borrar y marcar la inicial.
- Nexus Flow desplazable para perfiles con muchas capas.
- Los botones físicos presionados se iluminan en el control visual en tiempo real.
- Navegación con mouse o teclado: flechas, Enter, Ctrl+Z, Ctrl+Y, Ctrl+C, Ctrl+V, Ctrl+D, Ctrl+F y Supr.
- Los cambios siguen usando `AdvancedMapper`; no existe un segundo motor ni se duplican reglas.
- Límites defensivos de 32 capas, 16 reglas por entrada y ocho modificadores por acción.

## Apariencia Studio

- Presets **Nikaido**, **Cristal**, **Enfoque**, **AMOLED** y **Minimal**.
- Acentos Violeta, Cian, Rosa, Verde y Ámbar.
- Fondo con modos cubrir, contener o estirar.
- Posición superior, centrada o inferior.
- Zoom real entre 100 % y 180 %, oscurecimiento y viñeta.
- Transparencia separada para paneles, barra lateral y controles.
- Densidad cómoda o compacta.
- Reducción de movimiento.
- Barra lateral contraíble con estado persistente.
- Vista previa instantánea y aplicación agrupada para evitar tirones.
- El acento ahora también llega a gráficos pintados a mano, curvas y el control de Nexus.
- Las imágenes se orientan, validan, reducen y guardan de forma atómica en AppData.

## Flujo y rendimiento

- El Dashboard se construye al iniciar; las demás secciones se cargan cuando se abren por primera vez.
- El temporizador visual trabaja más rápido solo en páginas con telemetría en vivo y baja su frecuencia en pantallas estáticas.
- Una pantalla que falle al construirse queda aislada en una vista de error con reintento y acceso al diagnóstico.
- Paleta de comandos global con `Ctrl+K` para navegar, cambiar perfil, conectar, guardar, recentrar el gyro o aplicar un tema.
- Indicador permanente de cambios pendientes, guardado correcto o fallo de escritura.
- Las animaciones respetan la opción de reducción de movimiento.

## Perfiles y datos

- Guardado JSON atómico con `fsync` y reintentos breves para antivirus, indexadores o sincronizadores de Windows.
- Los paquetes `.Nika` se validan antes de modificar el perfil activo.
- Límites de tamaño, número de archivos, macros y efectos.
- Rechazo de archivos cifrados, miembros duplicados e imágenes falsas o gigantes.
- Importación transaccional: un recurso inválido no deja medio perfil instalado.
- Remapeo de IDs de macros importadas dentro de las reglas de Nexus.
- Exportación automática de macros referenciadas por Nexus aunque no estén marcadas manualmente para el perfil.
- Las referencias al propio perfil se actualizan al ID generado durante la importación.
- La versión del formato `.Nika` se mantiene en 1 y la configuración en 2.0.0.

## Estabilidad del ejecutable

- Mutex de Windows de 64 bits correctamente tipado para impedir dos instancias.
- Reportes locales limitados para errores del hilo principal y de workers.
- Errores de inicio visibles incluso en compilaciones `--noconsole`.
- Cierre idempotente de módulos después de una inicialización completa o parcial.
- Un fallo de la interfaz no cae en un modo consola invisible dentro del `.exe`.
- El build genera metadatos de versión, manifiesto SHA-256 y verifica:
  - runtime de Python;
  - backend HID nativo;
  - importación de pydualsense;
  - enumeración HID;
  - plugin `qwindows.dll`.

## Compatibilidad

No se cambió la ruta HID que ya detecta el DualSense, el orden de la IMU, ViGEm, el passthrough DS4 ni el formato de datos existente. Los perfiles, macros, calibraciones e Input Studio anteriores se conservan.

## Validación automatizada

- 170 pruebas aprobadas.
- Todos los archivos Python compilan sintácticamente.
- Validación del ZIP final antes de entregarlo.

La prueba física final del ejecutable, USB, Bluetooth, ViGEm y PySide6 debe realizarse en Windows con un DualSense real.
