from src.game_profile_watcher import GameProfileWatcher


class TriggerStub:
    def __init__(self, current="desktop"):
        self.current = current
        self.applied = []

    def apply_profile(self, profile_id):
        self.current = profile_id
        self.applied.append(profile_id)
        return True

    def get_current_profile(self):
        return self.current


def test_foreground_rule_wins_by_priority_and_restores_base_profile():
    foreground = {"pid": 10, "executable": "game.exe", "path": "", "title": "Game"}
    trigger = TriggerStub("desktop")
    watcher = GameProfileWatcher(trigger, foreground_provider=lambda: dict(foreground))
    watcher._running_processes = lambda: []
    watcher.set_rules(
        [
            {"id": "low", "executable": "game.exe", "profile_id": "low", "priority": 1},
            {"id": "high", "executable": "game.exe", "profile_id": "high", "priority": 9},
        ]
    )

    watcher._check_processes()
    assert trigger.applied == ["high"]
    assert watcher.get_diagnostics_snapshot()["base_profile"] == "desktop"

    foreground.clear()
    watcher._check_processes()
    assert trigger.applied == ["high", "desktop"]
    assert watcher.get_current_game() is None


def test_window_title_and_path_make_rule_specific():
    trigger = TriggerStub()
    foreground = {
        "pid": 1,
        "executable": "launcher.exe",
        "path": "/games/launcher.exe",
        "title": "My Game - DirectX 12",
    }
    watcher = GameProfileWatcher(trigger, foreground_provider=lambda: foreground)
    watcher._running_processes = lambda: []
    watcher.set_rules(
        [
            {
                "id": "specific",
                "executable": "launcher.exe",
                "path": "/games/launcher.exe",
                "window_title": "directx 12",
                "profile_id": "dx12",
            }
        ]
    )
    watcher._check_processes()
    assert trigger.applied == ["dx12"]


def test_manual_change_during_rule_becomes_restore_target():
    trigger = TriggerStub("desktop")
    foreground = {"pid": 2, "executable": "game.exe", "path": "", "title": "Game"}
    watcher = GameProfileWatcher(trigger, foreground_provider=lambda: dict(foreground))
    watcher._running_processes = lambda: []
    watcher.set_rules([{"id": "game", "executable": "game.exe", "profile_id": "auto"}])
    watcher._check_processes()

    trigger.current = "manual"
    watcher.observe_profile_change("manual")
    foreground.clear()
    watcher._check_processes()
    assert trigger.applied[-1] == "manual"
