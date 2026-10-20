# Asistente de bienvenida

El asistente de bienvenida se abre una vez en una instalación nueva o en una configuración que todavía no haya completado la versión actual del recorrido.

## Persistencia

Se guarda dentro de `settings.onboarding`:

```json
{
  "completed": true,
  "version": 1
}
```

Esto permite ampliar el recorrido en futuras versiones sin romper configuraciones anteriores.

## Reglas de comportamiento

- **Finalizar:** guarda ajustes, marca el recorrido como completado y abre la sección elegida.
- **Omitir:** marca el recorrido como completado, pero no aplica cambios temporales.
- **Cerrar el diálogo:** no marca el recorrido como completado; aparecerá en un inicio posterior.
- **Inicio minimizado:** el recorrido espera hasta que la ventana se muestre.
- **Reapertura manual:** Ajustes puede abrirlo aunque ya esté completado.

## Ajustes incluidos

El recorrido usa las mismas claves y motores que el resto de Nikaido. No existe una configuración paralela.

- `auto_connect`
- `start_minimized`
- `minimize_to_tray`
- `game_profiles_enabled`
- `vibration_enabled`
- `appearance`

## Apariencia

La vista previa usa `normalize_appearance()` y `NikaidoWindow.apply_appearance()`. Al cancelar se restaura el estado anterior. Al terminar, la pantalla de Ajustes también se sincroniza para evitar controles visualmente desactualizados.
