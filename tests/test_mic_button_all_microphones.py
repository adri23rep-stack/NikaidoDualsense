"""El botón MIC del control silencia por defecto cualquier micrófono del PC."""

from pathlib import Path

import pytest

from src.audio_manager import DEFAULT_TARGET_MODE, sanitize_audio_config
from src.profile_manager import ProfileManager
from src.trigger_engine import TriggerEngine

ROOT = Path(__file__).resolve().parents[1]
DEVICE_SOURCE = (ROOT / "gui" / "pages" / "device.py").read_text(encoding="utf-8")


def test_default_target_is_every_active_microphone():
    assert DEFAULT_TARGET_MODE == "all"
    assert sanitize_audio_config(None)["target_mode"] == "all"
    assert sanitize_audio_config({"device_id": "mic-x"})["target_mode"] == "all"
    assert sanitize_audio_config({"target_mode": ""})["target_mode"] == "all"


def test_explicit_choices_are_kept_and_garbage_falls_back_to_default():
    for mode in ("selected", "all", "all_except_dualsense"):
        assert sanitize_audio_config({"target_mode": mode})["target_mode"] == mode
    assert sanitize_audio_config({"target_mode": " ALL "})["target_mode"] == "all"
    assert sanitize_audio_config({"target_mode": "nuclear"})["target_mode"] == "all"


def test_new_profiles_and_app_defaults_use_every_microphone(tmp_path):
    manager = ProfileManager(str(tmp_path / "config"))
    assert manager.get_setting("audio.target_mode") == "all"
    engine = TriggerEngine()
    profiles = engine.get_all_profiles()
    assert profiles
    assert all(p.audio_config["target_mode"] == "all" for p in profiles.values())


def test_a_profile_saved_with_one_microphone_keeps_that_choice():
    saved = {"target_mode": "selected", "device_id": "usb-headset"}
    config = sanitize_audio_config(saved)
    assert config["target_mode"] == "selected"
    assert config["device_id"] == "usb-headset"


def test_audio_page_lists_all_microphones_first_and_can_apply_to_every_profile():
    order = [
        DEVICE_SOURCE.index('"Todos los micrófonos activos", "all"'),
        DEVICE_SOURCE.index('"Todos excepto el micrófono del DualSense", "all_except_dualsense"'),
        DEVICE_SOURCE.index('"Un micrófono específico", "selected"'),
    ]
    assert order == sorted(order)
    assert 'button("Usar esta opción en todos los perfiles", self.apply_target_to_all_profiles)' in DEVICE_SOURCE
    body = DEVICE_SOURCE.split("def apply_target_to_all_profiles", 1)[1].split("\n    def ", 1)[0]
    assert "engine.get_all_profiles()" in body
    assert 'config["target_mode"] = mode' in body
    # Solo copia el alcance: no toca micrófono, volumen ni estado inicial del perfil.
    for untouched in ("device_id", "volume", "profile_mute_mode"):
        assert f'config["{untouched}"]' not in body
    assert "_persist_now()" in body


def test_apply_to_all_profiles_copies_only_the_target_mode():
    pytest.importorskip("PySide6")
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from gui.pages.device import AudioPage

    engine = TriggerEngine()
    profiles = list(engine.get_all_profiles().values())
    profiles[0].audio_config = sanitize_audio_config(
        {"target_mode": "selected", "device_id": "usb-headset", "volume": 40}
    )
    toasts = []
    page = SimpleNamespace(
        window=SimpleNamespace(
            trigger_engine=engine,
            audio_manager=MagicMock(),
            language="es",
            toast=lambda message, kind="info": toasts.append(message),
        ),
        target_mode=SimpleNamespace(currentData=lambda: "all_except_dualsense"),
        _persist_now=MagicMock(),
    )

    AudioPage.apply_target_to_all_profiles(page)

    assert all(p.audio_config["target_mode"] == "all_except_dualsense" for p in engine.get_all_profiles().values())
    assert profiles[0].audio_config["device_id"] == "usb-headset"
    assert profiles[0].audio_config["volume"] == 40
    page._persist_now.assert_called_once()
    assert toasts == ["Aplicado a todos los perfiles"]

    toasts.clear()
    AudioPage.apply_target_to_all_profiles(page)
    assert toasts == ["Todos los perfiles ya usaban esta opción"]
