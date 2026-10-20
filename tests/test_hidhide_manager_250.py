from types import SimpleNamespace

from src.hidhide_manager import HidHideManager


DEVICE = r"HID\\VID_054C&PID_0CE6\\ABC"


class Runner:
    def __init__(self):
        self.calls = []

    def __call__(self, command, **_kwargs):
        self.calls.append(command)
        argument = command[1]
        outputs = {
            "--app-list": "C:\\Nikaido\\Nikaido.exe\n",
            "--dev-list": DEVICE + "\n",
            "--dev-gaming": DEVICE + "\n",
            "--cloak-state": "enabled\n",
        }
        return SimpleNamespace(returncode=0, stdout=outputs.get(argument, ""), stderr="")


def configured_manager(monkeypatch, tmp_path):
    runner = Runner()
    manager = HidHideManager(command_runner=runner)
    executable = tmp_path / "Nikaido.exe"
    executable.write_bytes(b"test")
    monkeypatch.setattr(manager, "is_supported", lambda: True)
    monkeypatch.setattr(manager, "_registry_info", lambda: ("1.5.0", r"C:\\HidHide"))
    monkeypatch.setattr(manager, "_find_tools", lambda _path="": (r"C:\\HidHideCLI.exe", r"C:\\HidHideClient.exe"))
    monkeypatch.setattr(manager, "current_executable", lambda: r"C:\\Nikaido\\Nikaido.exe")
    return manager, runner, executable


def test_scan_reports_ready_and_no_duplicate_risk(monkeypatch, tmp_path):
    manager, _runner, _executable = configured_manager(monkeypatch, tmp_path)
    snapshot = manager.scan(force=True, emulator_active=True)
    assert snapshot["installed"] is True
    assert snapshot["cloak_enabled"] is True
    assert snapshot["nikaido_whitelisted"] is True
    assert snapshot["dualsense_hidden"] == [DEVICE]
    assert snapshot["ready"] is True
    assert snapshot["duplicate_risk"] is False


def test_cli_actions_use_exact_safe_arguments(monkeypatch, tmp_path):
    manager, runner, executable = configured_manager(monkeypatch, tmp_path)
    monkeypatch.setattr(manager, "current_executable", lambda: str(executable))
    manager.whitelist_nikaido()
    manager.set_cloak_enabled(False)
    manager.set_device_hidden(DEVICE, True)
    flattened = [call[1:] for call in runner.calls]
    assert ["--app-reg", str(executable.resolve())] in flattened
    assert ["--cloak-off"] in flattened
    assert ["--dev-hide", DEVICE] in flattened


def test_state_parser_does_not_confuse_inactive_with_active():
    assert HidHideManager._state_from_text("inactivo") is False
    assert HidHideManager._state_from_text("desactivado") is False
    assert HidHideManager._state_from_text("enabled") is True
