import sys
from pathlib import Path


from src.audio_manager import PycawCaptureBackend
from src.hidhide_manager import HidHideManager
import src.hidhide_manager as hidhide_module


class _DelayedMuteEndpoint:
    def __init__(self):
        self.muted = False
        self.set_calls = 0

    def SetMute(self, value, _context):
        self.set_calls += 1
        # Simula un driver Bluetooth que ignora la primera escritura mientras
        # termina de activar el endpoint.
        if self.set_calls >= 2:
            self.muted = bool(value)

    def GetMute(self):
        return self.muted

    def GetMasterVolumeLevelScalar(self):
        raise OSError("volumen maestro no soportado")


class _Device:
    def __init__(self, device_id, name, endpoint):
        self.id = device_id
        self.FriendlyName = name
        self.EndpointVolume = endpoint


def test_capture_mute_is_retried_verified_and_does_not_require_volume(monkeypatch):
    endpoint = _DelayedMuteEndpoint()
    device = _Device("mic-usb", "Micrófono USB", endpoint)
    backend = PycawCaptureBackend()
    monkeypatch.setattr(
        backend,
        "_group_devices",
        lambda **_kwargs: [device],
    )

    states = backend.set_group_muted(True)

    assert endpoint.set_calls >= 2
    assert states[0].muted is True
    assert states[0].volume == 100


def test_hidhide_finds_current_vendor_folder_without_eu(monkeypatch, tmp_path):
    program_files = tmp_path / "Program Files"
    install = program_files / "Nefarius Software Solutions" / "HidHide" / "x64"
    install.mkdir(parents=True)
    cli = install / "HidHideCLI.exe"
    client = install / "HidHideClient.exe"
    cli.write_bytes(b"cli")
    client.write_bytes(b"client")

    monkeypatch.setenv("ProgramFiles", str(program_files))
    monkeypatch.delenv("ProgramW6432", raising=False)
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)

    found_cli, found_client = HidHideManager._find_tools("")
    assert Path(found_cli) == cli
    assert Path(found_client) == client


def test_hidhide_treats_driver_registry_fallback_as_installed(monkeypatch):
    manager = HidHideManager()
    monkeypatch.setattr(manager, "is_supported", lambda: True)
    monkeypatch.setattr(manager, "_registry_info", lambda: ("driver instalado", ""))
    monkeypatch.setattr(manager, "_find_tools", lambda _path="": ("", ""))

    snapshot = manager.scan(force=True)

    assert snapshot["installed"] is True
    assert "HidHide no está instalado" not in snapshot["issues"]
    assert "No se encontró HidHideCLI" in snapshot["issues"]


def test_source_runtime_uses_isolated_venv_python_for_hidhide(monkeypatch, tmp_path):
    executable = tmp_path / ".venv" / "Scripts" / "python.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"python")
    monkeypatch.setattr(hidhide_module.sys, "executable", str(executable))
    monkeypatch.setattr(hidhide_module.sys, "frozen", False, raising=False)

    assert Path(HidHideManager.current_executable()) == executable.resolve()


def test_global_python_is_not_auto_whitelisted(monkeypatch, tmp_path):
    executable = tmp_path / "Python310" / "python.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"python")
    monkeypatch.setattr(hidhide_module.sys, "executable", str(executable))
    monkeypatch.setattr(hidhide_module.sys, "frozen", False, raising=False)

    assert HidHideManager.current_executable() == ""


def test_hidhide_reads_machine_side_of_documented_hkcr_keys(monkeypatch):
    class Key:
        def __init__(self, path):
            self.path = path

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class FakeWinreg:
        HKEY_LOCAL_MACHINE = "HKLM"
        KEY_READ = 1
        KEY_WOW64_64KEY = 2
        KEY_WOW64_32KEY = 4

        @staticmethod
        def OpenKey(root, subkey, _reserved, _access):
            if root != "HKLM":
                raise OSError
            return Key(subkey)

        @staticmethod
        def QueryValueEx(key, value_name):
            values = {
                (
                    r"SOFTWARE\Classes\Installer\Dependencies\NSS.Drivers.HidHide.x64",
                    "Version",
                ): "1.5.230",
                (
                    r"SOFTWARE\Classes\SOFTWARE\Nefarius Software Solutions e.U.\Nefarius Software Solutions e.U. HidHide",
                    "Path",
                ): r"C:\Program Files\Nefarius Software Solutions\HidHide",
            }
            try:
                return values[(key.path, value_name)], 1
            except KeyError as exc:
                raise OSError from exc

    monkeypatch.setattr(hidhide_module.os, "name", "nt")
    monkeypatch.setitem(sys.modules, "winreg", FakeWinreg)

    assert HidHideManager._registry_info() == (
        "1.5.230",
        r"C:\Program Files\Nefarius Software Solutions\HidHide",
    )


def test_hidhide_accepts_short_managed_source_runtime(monkeypatch, tmp_path):
    local = tmp_path / "Local"
    executable = local / "NKB" / "rt" / "Scripts" / "python.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"python")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr(hidhide_module.sys, "executable", str(executable))
    monkeypatch.setattr(hidhide_module.sys, "frozen", False, raising=False)

    assert Path(HidHideManager.current_executable()) == executable.resolve()
