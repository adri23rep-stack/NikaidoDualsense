import json
from pathlib import Path
from types import SimpleNamespace

import src.hidhide_manager as hidhide_module
from src.hidhide_manager import HidHideManager


DUALSENSE_BASE = r"USB\VID_054C&PID_0CE6\ABC"
DUALSENSE_HID = r"HID\VID_054C&PID_0CE6&MI_03\ABC"


class StatefulHidHideRunner:
    def __init__(self, *, apps=None, hidden=None):
        self.apps = list(apps or [])
        self.hidden = list(hidden or [])
        self.cloak = False
        self.calls = []

    def __call__(self, command, **_kwargs):
        self.calls.append(command)
        action = command[1]
        if action == "--app-list":
            output = "\n".join(f'--app-reg "{item}"' for item in self.apps)
        elif action == "--app-reg":
            if command[2] not in self.apps:
                self.apps.append(command[2])
            output = ""
        elif action == "--app-unreg":
            target = command[2].casefold()
            self.apps = [item for item in self.apps if item.casefold() != target]
            output = ""
        elif action == "--dev-list":
            output = "\n".join(f'--dev-hide "{item}"' for item in self.hidden)
        elif action == "--dev-gaming":
            output = json.dumps(
                [
                    {
                        "friendlyName": "DualSense Wireless Controller",
                        "devices": [
                            {
                                "present": True,
                                "gamingDevice": True,
                                "vendor": "Sony Interactive Entertainment",
                                "product": "DualSense Wireless Controller",
                                "description": "Dispositivo de juego compatible con HID",
                                "deviceInstancePath": DUALSENSE_HID,
                                "xusbDeviceInstancePath": "",
                                "baseContainerDeviceInstancePath": DUALSENSE_BASE,
                            }
                        ],
                    }
                ]
            )
        elif action == "--cloak-state":
            output = "--cloak-on" if self.cloak else "--cloak-off"
        elif action == "--cloak-on":
            self.cloak = True
            output = ""
        elif action == "--cloak-off":
            self.cloak = False
            output = ""
        elif action == "--dev-hide":
            if command[2] not in self.hidden:
                self.hidden.append(command[2])
            output = ""
        elif action == "--dev-unhide":
            target = command[2].casefold()
            self.hidden = [item for item in self.hidden if item.casefold() != target]
            output = ""
        else:
            output = ""
        return SimpleNamespace(returncode=0, stdout=output, stderr="")


def configured_manager(monkeypatch, runner, executable):
    manager = HidHideManager(command_runner=runner)
    monkeypatch.setattr(manager, "is_supported", lambda: True)
    monkeypatch.setattr(manager, "_registry_info", lambda: ("1.5.230", r"C:\Program Files\HidHide"))
    monkeypatch.setattr(
        manager,
        "_find_tools",
        lambda _path="": (r"C:\Program Files\HidHide\HidHideCLI.exe", ""),
    )
    monkeypatch.setattr(manager, "current_executable", lambda: str(executable))
    return manager


def test_official_cli_script_output_is_parsed_and_reports_ready(monkeypatch, tmp_path):
    executable = tmp_path / "Nikaido.exe"
    executable.write_bytes(b"exe")
    runner = StatefulHidHideRunner(apps=[str(executable)], hidden=[DUALSENSE_BASE])
    runner.cloak = True
    manager = configured_manager(monkeypatch, runner, executable)

    snapshot = manager.scan(force=True, emulator_active=True)

    assert snapshot["applications"] == [str(executable)]
    assert snapshot["hidden_devices"] == [DUALSENSE_BASE]
    assert snapshot["dualsense_devices"] == [DUALSENSE_BASE]
    assert snapshot["dualsense_hidden"] == [DUALSENSE_BASE]
    assert snapshot["nikaido_whitelisted"] is True
    assert snapshot["ready"] is True
    assert snapshot["duplicate_risk"] is False


def test_enabling_hidhide_registers_compiled_exe_and_removes_stale_python(monkeypatch, tmp_path):
    executable = tmp_path / "Nikaido.exe"
    executable.write_bytes(b"exe")
    stale_python = tmp_path / "python.exe"
    runner = StatefulHidHideRunner(apps=[str(stale_python)])
    manager = configured_manager(monkeypatch, runner, executable)

    assert manager.set_cloak_enabled(True) is True

    actions = [call[1:] for call in runner.calls]
    assert ["--app-reg", str(executable.resolve())] in actions
    assert ["--app-unreg", str(stale_python)] in actions
    assert ["--cloak-on"] in actions
    assert actions.index(["--app-reg", str(executable.resolve())]) < actions.index(["--cloak-on"])
    assert str(executable.resolve()) in runner.apps
    assert str(stale_python) not in runner.apps


def test_compiled_executable_is_detected_without_sys_frozen(monkeypatch, tmp_path):
    executable = tmp_path / "Nikaido.exe"
    executable.write_bytes(b"exe")
    monkeypatch.setattr(hidhide_module.sys, "executable", str(executable))
    monkeypatch.setattr(hidhide_module.sys, "frozen", False, raising=False)

    assert Path(HidHideManager.current_executable()) == executable.resolve()


def test_bluetooth_device_instance_ids_are_accepted(monkeypatch, tmp_path):
    executable = tmp_path / "Nikaido.exe"
    executable.write_bytes(b"exe")
    runner = StatefulHidHideRunner(apps=[str(executable)])
    manager = configured_manager(monkeypatch, runner, executable)
    bluetooth_id = r"BTHENUM\DEV_001122334455\7&ABC&0&BLUETOOTHDEVICE_001122334455"

    manager.set_device_hidden(bluetooth_id, True)

    assert ["--dev-hide", bluetooth_id] in [call[1:] for call in runner.calls]
