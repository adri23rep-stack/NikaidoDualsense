"""Biblioteca de consejos del asistente Nikaido.

Separarla de la ventana principal mantiene la coordinación visual pequeña y
permite validar la bolsa aleatoria sin cargar PySide6.
"""

from __future__ import annotations

import random
from typing import Any, Sequence

ASSISTANT_TIPS = (
    ("quick_search", "compact_explaining", "El buscador rápido está escondido a simple vista",
     "Presiona Ctrl + K para saltar a cualquier sección sin recorrer la barra lateral.",
     "dashboard", "Entendido"),
    ("nexus_layers", "compact_thinking", "Nexus puede hacer más que cambiar botones",
     "Puedes crear capas, combinaciones, gestos y acciones de gyro desde el mismo mapa visual.",
     "mapper", "Abrir Nexus"),
    ("nika_profiles", "compact_explaining", "Los perfiles .Nika guardan casi todo",
     "Además de gatillos, pueden incluir luces, macros, gyro, vibración y ajustes de Input Studio.",
     "profiles", "Ver perfiles"),
    ("dashboard_favorites", "compact_happy", "Tu Dashboard puede ser más rápido",
     "Usa el lápiz de favoritos para agregar las secciones que abres seguido.",
     "dashboard", "Ver Dashboard"),
    ("double_input", "compact_thinking", "¿Notas doble entrada en algún juego?",
     "Compatibilidad incluye HidHide para que el juego no vea el control físico y el virtual al mismo tiempo.",
     "compatibility", "Abrir compatibilidad"),
    ("mouse_gyro_shortcut", "compact_explaining", "Mouse → Gyro tiene un atajo útil",
     "Cuando captures el mouse, Ctrl + M alterna la captura sin volver a la ventana.",
     "gyro", "Abrir Gyro Studio"),
    ("macro_sticks", "compact_happy", "Las macros también aceptan palancas",
     "Puedes editar tiempos, movimientos analógicos, combos y asignarlas a un perfil o botón.",
     "macros", "Abrir macros"),
    ("input_studio", "compact_explaining", "Input Studio no solo corrige drift",
     "También permite ajustar curvas, zonas muertas, recorrido y respuesta de cada palanca por perfil.",
     "input", "Abrir Input Studio"),
    ("diagnostics", "compact_thinking", "Diagnóstico puede ayudarte antes de reportar un bug",
     "Revisa latencia, lecturas, conflictos y copia un resumen seguro para soporte.",
     "monitor", "Abrir diagnóstico"),
    ("rumble_test", "compact_happy", "Puedes probar cada motor por separado",
     "En Vibración hay pruebas para el motor izquierdo, derecho o ambos sin abrir un juego.",
     "vibration", "Probar vibración"),
    ("game_rumble", "compact_explaining", "La vibración del juego puede volver al DualSense",
     "Activa la emulación y el puente de feedback para sentir lo que manda el juego al control virtual.",
     "vibration", "Ver vibración"),
    ("trigger_profiles", "compact_thinking", "Cada perfil puede tener gatillos distintos",
     "Guarda rigidez, zonas, pulsos y curvas diferentes para cada juego.",
     "triggers", "Abrir gatillos"),
    ("trigger_safe", "compact_explaining", "Un gatillo muy duro no siempre se siente mejor",
     "Prueba intensidades medias primero; suelen sentirse más naturales y cansan menos.",
     "triggers", "Ajustar gatillos"),
    ("rgb_effects", "compact_happy", "Las luces también viven dentro del perfil",
     "El color y los efectos pueden cambiar automáticamente cuando activas otro perfil.",
     "lights", "Abrir luces"),
    ("custom_lights", "compact_explaining", "Puedes crear tus propios efectos de luz",
     "Guarda una animación personalizada y reutilízala en distintos perfiles.",
     "lights", "Crear efecto"),
    ("battery", "compact_thinking", "Bluetooth consume más batería que USB",
     "Cuando estés ajustando muchas cosas, conecta el cable para evitar una desconexión a media prueba.",
     "dashboard", "Entendido"),
    ("profile_images", "compact_happy", "Tus perfiles pueden tener portada",
     "Usa una imagen propia para identificar cada juego sin depender de emojis.",
     "profiles", "Editar perfiles"),
    ("auto_profiles", "compact_explaining", "Nikaido puede detectar qué juego abriste",
     "Crea reglas por ejecutable para cambiar de perfil y restaurarlo cuando cierres el juego.",
     "automation", "Crear regla"),
    ("rule_priority", "compact_thinking", "La prioridad resuelve reglas que coinciden",
     "Si dos reglas detectan el mismo juego, la que tenga el número mayor gana.",
     "automation", "Ver reglas"),
    ("macro_delay", "compact_explaining", "Los tiempos pequeños cambian por completo una macro",
     "Ajusta cada pausa por separado cuando un juego no reconoce un combo rápido.",
     "macros", "Editar macros"),
    ("macro_profile", "compact_happy", "Una macro puede seguir a su perfil",
     "Así no tienes que activarla y desactivarla cada vez que cambias de juego.",
     "macros", "Ver macros"),
    ("gyro_calibration", "compact_thinking", "¿El gyro se mueve solo?",
     "Deja el control quieto y ejecuta la calibración antes de subir la sensibilidad.",
     "calibration", "Calibrar"),
    ("gyro_sensitivity", "compact_explaining", "Más sensibilidad no siempre significa más precisión",
     "Sube poco a poco y prueba una zona estable antes de cambiar otra opción.",
     "gyro", "Ajustar gyro"),
    ("drift", "compact_thinking", "Una zona muerta enorme también roba precisión",
     "Usa la calibración para encontrar el mínimo que realmente elimina el drift.",
     "calibration", "Calibrar sticks"),
    ("emulation_modes", "compact_explaining", "Xbox 360 y DualShock 4 sirven para cosas distintas",
     "Xbox suele tener mayor compatibilidad; DS4 conserva una salida tipo PlayStation.",
     "emulation", "Elegir emulación"),
    ("hidhide_allowlist", "compact_thinking", "HidHide debe permitir el Nikaido.exe correcto",
     "Si cambias de carpeta o versión, Compatibilidad puede revisar y reparar la entrada permitida.",
     "compatibility", "Revisar HidHide"),
    ("mic_button", "compact_happy", "El botón MIC puede silenciar tus entradas de Windows",
     "En Audio eliges si afecta al DualSense, a todos los micrófonos o a todos excepto el control.",
     "audio", "Abrir Audio"),
    ("mic_led", "compact_explaining", "El LED naranja también funciona como confirmación",
     "Cuando el silencio global está activo, Nikaido intenta mantener el LED MIC sincronizado.",
     "audio", "Ver Audio"),
    ("touchpad_mouse", "compact_happy", "El touchpad puede convertirse en mouse",
     "Ajusta sensibilidad y gesto de activación desde Emulación para no moverlo por accidente.",
     "emulation", "Configurar touchpad"),
    ("keybridge", "compact_explaining", "KeyBridge convierte teclado y mouse en control virtual",
     "Es útil para probar perfiles incluso cuando el DualSense no está conectado.",
     "emulation", "Abrir KeyBridge"),
    ("backup", "compact_thinking", "Nikaido crea respaldos de tu configuración",
     "Tus perfiles y ajustes viven fuera de la carpeta del programa para sobrevivir actualizaciones.",
     "settings", "Ver ajustes"),
    ("updates", "compact_happy", "Las actualizaciones ya no requieren desinstalar",
     "Cuando exista una versión nueva, Ajustes podrá descargarla y conservar tus perfiles.",
     "settings", "Buscar actualización"),
    ("tip_sound", "compact_explaining", "Este sonido se puede apagar",
     "En Ajustes puedes dejar los consejos visibles sin reproducir el aviso.",
     "settings", "Configurar consejos"),
    ("clean_report", "compact_thinking", "El reporte de diagnóstico protege tus rutas personales",
     "Antes de guardarlo, Nikaido elimina nombres de usuario y ubicaciones privadas conocidas.",
     "monitor", "Copiar diagnóstico"),
    ("usb_bt_profiles", "compact_explaining", "Prueba USB y Bluetooth antes de culpar al perfil",
     "Una diferencia entre conexiones ayuda a saber si el problema viene del perfil o del transporte.",
     "tools", "Abrir herramientas"),
    ("release_beta", "compact_happy", "Gracias por probar la beta de Nikaido",
     "Los reportes claros ayudan a convertir esta primera versión pública en algo mucho más estable.",
     "monitor", "Abrir diagnóstico"),
)


def take_assistant_tip(
    remaining_ids: Any,
    last_id: str = "",
    *,
    rng: Any = None,
) -> tuple[tuple[str, str, str, str, str, str], list[str]]:
    """Toma un consejo de una bolsa válida sin repetir al reiniciarla."""
    by_id = {tip[0]: tip for tip in ASSISTANT_TIPS}
    remaining: list[str] = []
    if isinstance(remaining_ids, Sequence) and not isinstance(remaining_ids, (str, bytes)):
        for item in remaining_ids:
            tip_id = str(item)
            if tip_id in by_id and tip_id not in remaining:
                remaining.append(tip_id)
    if not remaining:
        remaining = list(by_id)
        (rng or random.SystemRandom()).shuffle(remaining)
        if len(remaining) > 1 and remaining[0] == str(last_id or ""):
            remaining[0], remaining[1] = remaining[1], remaining[0]
    tip_id = remaining.pop(0)
    return by_id[tip_id], remaining
