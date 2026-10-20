from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
PROFILE = (ROOT / "src" / "profile_manager.py").read_text(encoding="utf-8")
VERSION = (ROOT / "nikaido_version.py").read_text(encoding="utf-8")


def test_25_version_and_defaults_are_consistent():
    from nikaido_version import APP_VERSION

    assert f'APP_VERSION = "{APP_VERSION}"' in VERSION
    assert "'virtual_feedback': {" in PROFILE
    assert "'game_profile_rules': []" in PROFILE
    assert "'hidhide': {" in PROFILE


def test_new_backends_are_started_persisted_and_stopped():
    assert "VirtualFeedbackBridge(" in MAIN
    assert "HidHideManager()" in MAIN
    assert "self.virtual_feedback_bridge.start()" in MAIN
    assert "'game_profile_rules', self.game_profile_watcher.get_rules()" in MAIN
    assert '"feedback virtual", lambda: self.virtual_feedback_bridge.stop()' in MAIN
    assert "game_profile_watcher.observe_profile_change" in MAIN
