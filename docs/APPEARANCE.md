# Apariencia Studio

Apariencia Studio personaliza Nikaido sin mezclar la presentación con los motores HID. Las preferencias se normalizan en `src/appearance.py` y la interfaz las aplica desde `gui/design_system.py`.

## Presets y acentos

Presets incluidos:

- **Nikaido:** equilibrio predeterminado.
- **Cristal:** paneles más transparentes para destacar el fondo.
- **Enfoque:** mayor opacidad y contraste.
- **AMOLED:** superficies sólidas, compactas y muy oscuras.
- **Minimal:** densidad compacta y menos peso visual.

Acentos disponibles: Violeta Nikaido, Cian eléctrico, Rosa neón, Verde aurora y Ámbar. El acento se aplica tanto a controles Qt como a gráficos dibujados manualmente, por ejemplo sticks, curvas y Nexus.

## Fondo personalizado

Se admiten PNG, JPG, JPEG, WEBP y BMP. La imagen se:

1. verifica con Pillow;
2. orienta usando sus datos EXIF;
3. limita a 4096 × 4096;
4. convierte a PNG si necesita transparencia o JPEG optimizado si no;
5. escribe de forma atómica en `%APPDATA%/DualSenseController/ui_backgrounds`.

El archivo original puede moverse o borrarse después.

## Fondos incluidos

Nikaido trae seis fondos listos para usar (Monte Roraima, Delta del Amazonas, Valle del Pati, Volcán Villarrica, Lençóis Maranhenses y Neuquén). Son imágenes satelitales Landsat de dominio público publicadas bajo CC0 por Leonardo Uieda; los créditos y la licencia están en `assets/wallpapers/`.

Se eligen con un clic desde la galería del asistente de bienvenida y desde Ajustes > Apariencia. Al elegir uno se copia como cualquier fondo propio (mismo flujo de validación y optimización), así que los controles de ajuste, zoom, oscurecimiento y viñeta funcionan igual. Elegir una imagen propia o quitar el fondo olvida la selección.

## Controles

- Activar o desactivar el fondo.
- Cubrir, contener o estirar.
- Alinear arriba, al centro o abajo.
- Zoom de 100 % a 180 %.
- Oscurecimiento y viñeta.
- Opacidad independiente de paneles, sidebar y botones.
- Densidad cómoda o compacta.
- Reducción de movimiento.
- Barra lateral contraída o expandida.

## Rendimiento

- El fondo escalado usa caché por tamaño, modo, zoom, ruta, fecha y tamaño del archivo.
- Reemplazar una imagen en la misma ruta invalida correctamente la caché.
- Mover sliders de fondo solo repinta el lienzo; no reconstruye toda la hoja visual.
- Los cambios de estilo se agrupan durante 90 ms.
- Las listas flotantes y menús permanecen opacos para conservar legibilidad.

## Restauración

Restablecer apariencia recupera los valores originales. El restablecimiento completo de Nikaido también puede limpiar fondos y miniaturas huérfanas.
