from __future__ import annotations

import time
from pathlib import Path

from src.light_effects import (
    EFFECT_SPECS,
    LightEffectEngine,
    sample_light_effect,
    sanitize_light_config,
)

ROOT = Path(__file__).resolve().parents[1]


class DummyConnection:
    def __init__(self) -> None:
        self.colors: list[tuple[int, int, int]] = []

    def set_led_color(self, red: int, green: int, blue: int) -> None:
        self.colors.append((red, green, blue))


def test_all_builtin_rgb_studio_effects_generate_safe_complete_samples():
    base = {
        "color": [67, 215, 239],
        "secondary_color": [198, 63, 244],
        "brightness": 0.9,
        "intensity": 0.85,
        "speed": 1.3,
        "direction": 1,
        "palette": [[123, 63, 242], [255, 77, 214], [67, 215, 239]],
    }
    for effect_id in EFFECT_SPECS:
        config = {**base, "effect": effect_id}
        if effect_id == "custom":
            config["custom_id"] = "neon"
        for elapsed in (0.0, 0.13, 0.41, 0.87, 1.42):
            sample = sample_light_effect(
                config,
                elapsed,
                custom_effects={
                    "neon": {
                        "name": "Neon",
                        "palette": [[255, 0, 120], [0, 220, 255]],
                        "speed": 1.4,
                    }
                },
                audio_level=0.62,
                segment_count=9,
            )
            assert len(sample.segments) == 9
            assert 0.0 <= sample.progress <= 1.0
            assert 0.0 <= sample.level <= 1.0
            assert all(0 <= channel <= 255 for channel in sample.color)
            assert all(
                0 <= channel <= 255
                for segment in sample.segments
                for channel in segment
            )


def test_new_light_settings_are_sanitized_without_breaking_old_profiles():
    legacy = sanitize_light_config(
        {
            "effect": "wave",
            "color": [1, 2, 3],
            "secondary_color": [4, 5, 6],
            "speed": 2.5,
            "brightness": 0.7,
        }
    )
    assert legacy["effect"] == "wave"
    assert legacy["intensity"] == 1.0
    assert legacy["direction"] == 1
    assert legacy["smoothing"] == 0.18
    assert legacy["audio_gain"] == 1.6

    hostile = sanitize_light_config(
        {
            "effect": "not-real",
            "intensity": 999,
            "direction": -200,
            "smoothing": 999,
            "audio_gain": -5,
            "audio_floor": 20,
        }
    )
    assert hostile["effect"] == "static"
    assert hostile["intensity"] == 1.0
    assert hostile["direction"] == -1
    assert hostile["smoothing"] == 0.95
    assert hostile["audio_gain"] == 0.25
    assert hostile["audio_floor"] == 0.35


def test_direction_reverses_wave_progress_and_color_order():
    common = {
        "effect": "wave",
        "color": [255, 0, 0],
        "secondary_color": [0, 0, 255],
        "speed": 1.0,
        "brightness": 1.0,
    }
    forward = sample_light_effect({**common, "direction": 1}, 0.17)
    reverse = sample_light_effect({**common, "direction": -1}, 0.17)
    assert forward.progress != reverse.progress
    assert forward.color != reverse.color
    assert forward.segments != reverse.segments


def test_audio_reactive_effect_uses_injected_real_level_provider():
    connection = DummyConnection()
    levels = iter([0.1, 0.65, 0.9, 0.3, 0.8, 0.2])

    def provider() -> float:
        try:
            return next(levels)
        except StopIteration:
            return 0.55

    engine = LightEffectEngine(connection, fps=60, audio_level_provider=provider)
    engine.apply_config(
        {
            "effect": "audio",
            "color": [0, 100, 255],
            "secondary_color": [255, 0, 160],
            "audio_gain": 1.8,
            "smoothing": 0.05,
        }
    )
    time.sleep(0.09)
    status = engine.get_audio_status()
    engine.shutdown()

    assert connection.colors
    assert len(set(connection.colors)) >= 2
    assert status["available"] is True
    assert status["level"] > 0.0
    assert status["error"] == ""


def test_rgb_studio_uses_one_shared_preview_clock_and_modular_widgets():
    page_source = (ROOT / "gui" / "pages" / "device.py").read_text(encoding="utf-8")
    studio_source = (ROOT / "gui" / "light_studio.py").read_text(encoding="utf-8")
    build_source = (ROOT / "build.py").read_text(encoding="utf-8")

    assert "PREVIEW_INTERVAL_MS = 33" in page_source
    assert "self._preview_timer = QTimer(self)" in page_source
    assert "class EffectTile" in studio_source
    assert "class LightTimelinePreview" in studio_source
    assert "QTimer(" not in studio_source
    assert '"gui.light_studio"' in build_source
    assert '"gui.controller_visual"' in build_source
