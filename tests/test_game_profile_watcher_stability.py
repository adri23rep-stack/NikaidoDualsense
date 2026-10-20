from types import SimpleNamespace

import src.game_profile_watcher as watcher_module
from src.game_profile_watcher import GameProfileWatcher


class TriggerStub:
    def __init__(self):
        self.applied = []

    def apply_profile(self, profile_id):
        self.applied.append(profile_id)
        return True


class ProcessList:
    def __init__(self, names):
        self.names = names

    def process_iter(self, _fields):
        return [SimpleNamespace(info={"name": name}) for name in self.names]


def test_mapping_change_for_same_executable_reapplies_profile(monkeypatch):
    trigger = TriggerStub()
    watcher = GameProfileWatcher(trigger)
    events = []
    watcher.on_game_change(lambda exe, profile: events.append((exe, profile)))
    monkeypatch.setattr(watcher_module, "psutil", ProcessList(["game.exe"]))

    watcher.set_mapping({"game.exe": "profile_a"})
    watcher._check_processes()
    watcher.set_mapping({"game.exe": "profile_b"})
    watcher._check_processes()

    assert trigger.applied == ["profile_a", "profile_b"]
    assert events[-1] == ("game.exe", "profile_b")


def test_clearing_mapping_clears_stale_game(monkeypatch):
    watcher = GameProfileWatcher(TriggerStub())
    events = []
    watcher.on_game_change(lambda exe, profile: events.append((exe, profile)))
    monkeypatch.setattr(watcher_module, "psutil", ProcessList(["game.exe"]))

    watcher.set_mapping({"game.exe": "profile_a"})
    watcher._check_processes()
    watcher.set_mapping({})
    watcher._check_processes()

    assert watcher.get_current_game() is None
    assert events[-1] == (None, None)
