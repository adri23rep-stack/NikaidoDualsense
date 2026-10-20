from pathlib import Path
from types import SimpleNamespace
import time

from src.light_effects import LightEffectEngine
from src.player_led_battery import (
    PLAYER_PATTERNS,
    PlayerLedBatteryController,
    battery_segments,
    sanitize_player_led_config,
)
from src.trigger_engine import TRIGGER_PRESETS, TriggerEffectType, effect_from_preset

ROOT = Path(__file__).resolve().parents[1]


class FakeConnection:
    def __init__(self):
        self.is_connected = True
        self.patterns = []
        self.colors = []
        self._connect = []
        self._disconnect = []
        self._battery = []
        self.level = 80
        self.status = SimpleNamespace(value="descargando")

    def on_connect(self, callback):
        self._connect.append(callback)

    def on_disconnect(self, callback):
        self._disconnect.append(callback)

    def on_battery_change(self, callback):
        self._battery.append(callback)

    def get_battery_info(self):
        return self.level, self.status

    def set_player_led_pattern(self, pattern):
        self.patterns.append(pattern)
        return True

    def set_led_color(self, red, green, blue):
        self.colors.append((red, green, blue))
        return True

    def emit_battery(self, level, status):
        self.level = level
        self.status = SimpleNamespace(value=status)
        for callback in self._battery:
            callback(level, self.status)


def test_battery_segments_use_four_clear_levels():
    assert battery_segments(0) == 1
    assert battery_segments(25) == 1
    assert battery_segments(26) == 2
    assert battery_segments(50) == 2
    assert battery_segments(51) == 3
    assert battery_segments(75) == 3
    assert battery_segments(76) == 4
    assert battery_segments(100) == 4


def test_player_led_config_is_sanitized():
    config = sanitize_player_led_config(
        {"mode": "invalid", "player_number": 99, "critical_percent": -3}
    )
    assert config["mode"] == "battery"
    assert config["player_number"] == 5
    assert config["critical_percent"] == 1


def test_battery_controller_updates_player_patterns_without_touching_rgb():
    connection = FakeConnection()
    controller = PlayerLedBatteryController(
        connection,
        {"mode": "battery", "charging_animation": False, "critical_blink": False},
    )
    try:
        connection.emit_battery(100, "descargando")
        assert connection.patterns[-1] == PLAYER_PATTERNS[4]
        connection.emit_battery(52, "descargando")
        assert connection.patterns[-1] == PLAYER_PATTERNS[3]
        connection.emit_battery(30, "descargando")
        assert connection.patterns[-1] == PLAYER_PATTERNS[2]
        connection.emit_battery(8, "descargando")
        assert connection.patterns[-1] == PLAYER_PATTERNS[1]
        assert connection.colors == []
    finally:
        controller.stop()


def test_player_led_game_mode_relinquishes_output():
    connection = FakeConnection()
    controller = PlayerLedBatteryController(connection, {"mode": "game"})
    try:
        connection.patterns.clear()
        connection.emit_battery(60, "descargando")
        assert connection.patterns == []
    finally:
        controller.stop()


def test_light_control_game_mode_blocks_nikaido_writes():
    connection = FakeConnection()
    engine = LightEffectEngine(connection)
    engine.set_control_mode("game")
    engine.apply_config({"effect": "static", "color": [1, 2, 3]})
    engine._send_color((4, 5, 6), force=True)
    engine.shutdown()
    assert connection.colors == []


def test_light_control_balanced_mode_keeps_legacy_one_shot_static():
    connection = FakeConnection()
    engine = LightEffectEngine(connection)
    engine.set_control_mode("balanced")
    engine.apply_config({"effect": "static", "color": [11, 22, 33]})
    engine.shutdown()
    assert connection.colors[-1] == (11, 22, 33)


def test_trigger_studio_has_rich_safe_preset_library():
    assert len(TRIGGER_PRESETS) >= 18
    assert {preset.category for preset in TRIGGER_PRESETS.values()} >= {
        "Básicos", "Armas", "Vehículos", "Mecánicos"
    }
    bow = effect_from_preset("bow")
    assert bow.effect_type is TriggerEffectType.SECTIONS
    assert len(bow.custom_params["sections"]) >= 4
    abs_effect = effect_from_preset("abs")
    assert abs_effect.effect_type is TriggerEffectType.CONTINUOUS_VIBRATION
    assert 1 <= abs_effect.frequency <= 255


def test_trigger_studio_ui_contains_new_workflow():
    source = (ROOT / "gui" / "pages" / "triggers.py").read_text(encoding="utf-8")
    assert "BIBLIOTECA DE SENSACIONES" in source
    assert "Vincular L2 y R2" in source
    assert "Recorrido físico" in source
    assert "Probar efecto real" in source
    assert "Copiar a R2" in source


def test_release_version_is_2980():
    version_source = (ROOT / "nikaido_version.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "2.9.8.13"' in version_source


def test_unknown_battery_does_not_flash_false_critical_state():
    connection = FakeConnection()
    connection.level = 0
    connection.status = SimpleNamespace(value="desconocido")
    controller = PlayerLedBatteryController(connection, {"mode": "battery"})
    try:
        time.sleep(0.02)
        assert connection.patterns == []
        connection.emit_battery(8, "descargando")
        assert connection.patterns
    finally:
        controller.stop()


def test_light_writer_retries_equal_color_after_explicit_failure():
    class FlakyConnection(FakeConnection):
        def __init__(self):
            super().__init__()
            self.attempts = 0

        def set_led_color(self, red, green, blue):
            self.attempts += 1
            self.colors.append((red, green, blue))
            return self.attempts > 1

    connection = FlakyConnection()
    engine = LightEffectEngine(connection)
    try:
        engine._send_color((7, 8, 9))
        engine._send_color((7, 8, 9))
        assert connection.attempts == 2
    finally:
        engine.shutdown()
