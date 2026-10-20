"""El aviso sonoro del asistente no debe sonar con Nikaido minimizado o al fondo."""

import sys
import types
from unittest.mock import MagicMock

import pytest

from src import ui_sounds

pytest.importorskip("PySide6")
main_window = pytest.importorskip("gui.main_window")
assistant = pytest.importorskip("gui.assistant")
from PySide6.QtCore import Qt  # noqa: E402

NikaidoWindow = main_window.NikaidoWindow


class _FakeApp:
    def __init__(self, state):
        self._state = state

    def applicationState(self):
        return self._state


class _FakeQApplication:
    state = Qt.ApplicationState.ApplicationActive

    @classmethod
    def instance(cls):
        return _FakeApp(cls.state)


def _window(*, visible=True, minimized=False, state=Qt.WindowState.WindowNoState, active=True):
    win = MagicMock()
    win._stopping = False
    win.isVisible.return_value = visible
    win.isMinimized.return_value = minimized
    win.windowState.return_value = state
    win.isActiveWindow.return_value = active
    return win


@pytest.fixture(autouse=True)
def _active_app(monkeypatch):
    _FakeQApplication.state = Qt.ApplicationState.ApplicationActive
    monkeypatch.setattr(assistant, "QApplication", _FakeQApplication)


def test_in_front_only_when_visible_active_and_not_minimized():
    assert assistant.window_is_in_front(_window()) is True
    assert assistant.window_is_in_front(_window(visible=False)) is False
    assert assistant.window_is_in_front(_window(minimized=True)) is False
    # Windows a veces avisa tarde: el estado dice minimizado aunque isMinimized() aún no.
    assert assistant.window_is_in_front(_window(state=Qt.WindowState.WindowMinimized)) is False
    # Detrás de un juego u otra app: la ventana existe pero no está activa.
    assert assistant.window_is_in_front(_window(active=False)) is False
    stopping = _window()
    stopping._stopping = True
    assert assistant.window_is_in_front(stopping) is False


def test_in_front_is_false_when_the_whole_app_is_inactive():
    _FakeQApplication.state = Qt.ApplicationState.ApplicationInactive
    assert assistant.window_is_in_front(_window()) is False


def _tip_window(monkeypatch, *, in_front, sounds=True, minimized=False):
    played = []
    monkeypatch.setattr(main_window, "play_tip_sound", lambda: played.append(1))
    win = MagicMock()
    win._stopping = False
    win._welcome_wizard = None
    win.language = "es"
    win.is_assistant_enabled.return_value = True
    win.isVisible.return_value = True
    win.isMinimized.return_value = minimized
    monkeypatch.setattr(main_window, "window_is_in_front", lambda _window: in_front)
    win._take_assistant_tip.return_value = ("id", "neutral", "Titulo", "Mensaje", "dashboard", "Abrir")
    settings = {"assistant.tips_enabled": True, "assistant.tip_sounds_enabled": sounds}
    win.profile_manager.get_setting.side_effect = lambda key, default=None: settings.get(key, default)
    return win, played


def test_tip_sound_is_muted_when_window_is_not_in_front(monkeypatch):
    win, played = _tip_window(monkeypatch, in_front=False)
    NikaidoWindow.show_next_assistant_tip(win)
    assert played == []


def test_tip_sound_plays_when_window_is_in_front(monkeypatch):
    win, played = _tip_window(monkeypatch, in_front=True)
    NikaidoWindow.show_next_assistant_tip(win)
    assert played == [1]


def test_tip_sound_respects_the_setting(monkeypatch):
    win, played = _tip_window(monkeypatch, in_front=True, sounds=False)
    NikaidoWindow.show_next_assistant_tip(win)
    assert played == []


def test_minimized_window_skips_the_tip_and_retries_later(monkeypatch):
    win, played = _tip_window(monkeypatch, in_front=True, minimized=True)
    NikaidoWindow.show_next_assistant_tip(win)
    assert played == []
    win._take_assistant_tip.assert_not_called()
    win.assistant_timer.start.assert_called_once_with(120_000)


def test_hiding_the_tip_and_minimizing_cut_the_sound():
    source = (main_window.__file__ and open(main_window.__file__, encoding="utf-8").read())
    hide_body = source.split("def hide_assistant_tip", 1)[1].split("\n    def ", 1)[0]
    assert "stop_tip_sound()" in hide_body
    change_body = source.split("def changeEvent", 1)[1].split("\n    def ", 1)[0]
    assert "WindowMinimized" in change_body and "stop_tip_sound()" in change_body
    assert "def hideEvent" in source


def test_stop_tip_sound_purges_on_windows(monkeypatch):
    calls = []
    fake = types.SimpleNamespace(SND_PURGE=64, PlaySound=lambda *args: calls.append(args))
    monkeypatch.setitem(sys.modules, "winsound", fake)
    monkeypatch.setattr(ui_sounds.os, "name", "nt")
    ui_sounds.stop_tip_sound()
    assert calls == [(None, 64)]


def test_stop_tip_sound_is_a_noop_elsewhere(monkeypatch):
    calls = []
    fake = types.SimpleNamespace(SND_PURGE=64, PlaySound=lambda *args: calls.append(args))
    monkeypatch.setitem(sys.modules, "winsound", fake)
    monkeypatch.setattr(ui_sounds.os, "name", "posix")
    ui_sounds.stop_tip_sound()
    assert calls == []
