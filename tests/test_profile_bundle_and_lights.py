import json
import time
from pathlib import Path

from PIL import Image

from src.input_studio import InputStudioEngine
from src.light_effects import LightEffectEngine, parse_palette
from src.profile_manager import ProfileManager
from src.trigger_engine import TriggerEffectType, TriggerEngine


class DummyConnection:
    def __init__(self):
        self.colors = []

    def set_led_color(self, r, g, b):
        self.colors.append((r, g, b))


def test_light_engine_presets_and_custom_effects():
    connection = DummyConnection()
    engine = LightEffectEngine(connection, fps=60)
    custom_id = engine.register_custom_effect(
        "Neon", "#ff0000, #00ff00, #0000ff", speed=2.0
    )
    engine.apply_config({"effect": "rainbow", "speed": 2, "brightness": 0.5})
    time.sleep(0.04)
    assert connection.colors
    assert all(0 <= channel <= 255 for color in connection.colors for channel in color)

    config = engine.apply_config({"effect": f"custom:{custom_id}"})
    assert config["effect"] == "custom"
    assert config["custom_id"] == custom_id
    engine.shutdown()


def test_palette_parser_ignores_invalid_values():
    assert parse_palette("nope, #FF0000, #00ff00") == [[255, 0, 0], [0, 255, 0]]


def test_profile_overrides_round_trip_full_profile():
    first = TriggerEngine()
    profile = first.get_profile("sniper")
    profile.image_path = "C:/profiles/sniper.png"
    profile.macros_enabled = False
    profile.rumble_intensity = 211
    profile.light_config = {
        "effect": "wave",
        "color": [1, 2, 3],
        "secondary_color": [4, 5, 6],
        "speed": 1.7,
        "brightness": 0.8,
        "palette": [],
        "custom_id": "",
    }
    profile.right_trigger.effect_type = TriggerEffectType.SECTIONS
    profile.right_trigger.custom_params["sections"] = [[0, 30], [3, 90], [6, 180], [9, 255]]

    second = TriggerEngine()
    second.load_profile_overrides(first.export_profile_overrides())
    restored = second.get_profile("sniper")
    assert restored.image_path.endswith("sniper.png")
    assert restored.macros_enabled is False
    assert restored.rumble_intensity == 211
    assert restored.light_config["effect"] == "wave"
    assert restored.right_trigger.effect_type is TriggerEffectType.SECTIONS
    assert restored.right_trigger.custom_params["sections"][2] == [6, 180]


def test_profile_bundle_keeps_image_and_input_studio(tmp_path):
    manager = ProfileManager(str(tmp_path / "config"))
    image = tmp_path / "cover.png"
    Image.new("RGB", (96, 64), (42, 76, 122)).save(image)

    engine = TriggerEngine()
    profile = engine.get_profile("sniper")
    profile.image_path = str(image)
    studio = InputStudioEngine()
    studio.update_config("sniper", "right", curve="aggressive", sensitivity_x=1.8)
    profile.input_studio_config = studio.get_profile_config("sniper")

    exported = tmp_path / "sniper.json"
    assert manager.export_profile("sniper", str(exported), profile.to_dict())
    payload = json.loads(exported.read_text(encoding="utf-8"))
    assert payload["version"] == "2.0"
    assert payload["image_data"]
    assert payload["profile"]["input_studio"]["right"]["curve"] == "aggressive"

    imported_id = manager.import_profile(str(exported))
    imported = manager.get_custom_profiles()[imported_id]
    assert Path(imported["image_path"]).is_file()
    assert imported["input_studio"]["right"]["sensitivity_x"] == 1.8


def test_light_engine_concurrent_restart_keeps_one_worker():
    import threading

    engine = LightEffectEngine(DummyConnection(), fps=60)
    engine.apply_config({"effect": "rainbow"})
    engine.stop()
    gate = threading.Barrier(9)

    def starter():
        gate.wait()
        engine.start()

    workers = [threading.Thread(target=starter) for _ in range(8)]
    for worker in workers:
        worker.start()
    gate.wait()
    for worker in workers:
        worker.join(1.0)

    assert engine._thread is not None and engine._thread.is_alive()
    assert len([
        thread for thread in threading.enumerate()
        if thread.name == "DualSenseLightEffects" and thread.is_alive()
    ]) == 1
    engine.shutdown()
