"""Regresiones del asistente global de Nikaido 2.8.0."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = (ROOT / "gui" / "pages" / "settings.py").read_text(encoding="utf-8")
MAIN = (ROOT / "gui" / "main_window.py").read_text(encoding="utf-8")
ASSISTANT = (ROOT / "gui" / "assistant.py").read_text(encoding="utf-8")
TIPS = (ROOT / "gui" / "assistant_tips.py").read_text(encoding="utf-8")
PROFILE = (ROOT / "src" / "profile_manager.py").read_text(encoding="utf-8")


def test_wizard_asks_for_assistant_after_finish_and_skip():
    assert "class AssistantChoiceDialog(QDialog):" in SETTINGS
    assert '"¿Quieres a Nikaido como tu asistente?"' in SETTINGS
    assert '"¿Por qué? 😭"' in SETTINGS
    assert SETTINGS.count("self._ask_assistant_choice()") >= 2


def test_global_assistant_has_contextual_tips_and_is_optional():
    assert "ASSISTANT_TIPS = ASSISTANT_TIP_LIBRARY" in MAIN
    assert (ROOT / "gui" / "assistant_tips.py").is_file()
    assert "Ctrl + K" in TIPS
    assert "HidHide" in TIPS
    assert "Mouse → Gyro" in TIPS
    assert 'get_setting("assistant.enabled", False)' in MAIN
    assert "assistant_timer" in MAIN


def test_assistant_card_is_separate_and_memory_friendly():
    assert "class AssistantTipCard(QFrame):" in ASSISTANT
    assert "load_scaled_pixmap" in ASSISTANT
    assert "clear_resources" in ASSISTANT


def test_assistant_settings_have_safe_defaults():
    assert "'assistant': {" in PROFILE
    assert "'enabled': False" in PROFILE
    assert "'choice_made': False" in PROFILE
    assert "'tip_interval_minutes': 12" in PROFILE
