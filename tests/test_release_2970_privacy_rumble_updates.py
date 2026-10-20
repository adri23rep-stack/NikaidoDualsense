from __future__ import annotations

import hashlib
import io
import json
import time
from pathlib import Path

import build
from gui.assistant_tips import ASSISTANT_TIPS, take_assistant_tip
from nikaido_version import APP_VERSION, RELEASE_STAGE
from src.connection_manager import ConnectionManager
from src.update_manager import UpdateInfo, UpdateManager, is_newer_version, parse_manifest

ROOT = Path(__file__).resolve().parents[1]


class _FakeController:
    def __init__(self) -> None:
        self.leftMotor = 0
        self.rightMotor = 0
        self.calls: list[tuple[str, int]] = []

    def setLeftMotor(self, value: int) -> None:
        self.leftMotor = value
        self.calls.append(("left", value))

    def setRightMotor(self, value: int) -> None:
        self.rightMotor = value
        self.calls.append(("right", value))


class _Response(io.BytesIO):
    def __init__(self, payload: bytes) -> None:
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
        return False


def test_release_identity_uses_only_team_branding():
    assert APP_VERSION == "2.9.8.13"
    assert RELEASE_STAGE == "Beta 1"
    installer = (ROOT / "installer" / "Nikaido.iss").read_text(encoding="utf-8")
    version_info = build.write_version_info().read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "AppPublisher=Team Nikaido" in installer
    assert "VersionInfoCompany=Team Nikaido" in installer
    assert "CompanyName', 'Team Nikaido" in version_info
    assert 'authors = [{ name = "Team Nikaido" }]' in pyproject


def test_assistant_tip_library_is_large_unique_and_has_sound_setting():
    ids = [tip[0] for tip in ASSISTANT_TIPS]
    assert len(ids) >= 30
    assert len(ids) == len(set(ids))
    assert all(len(tip) == 6 for tip in ASSISTANT_TIPS)
    profile_source = (ROOT / "src" / "profile_manager.py").read_text(encoding="utf-8")
    settings_source = (ROOT / "gui" / "pages" / "settings.py").read_text(encoding="utf-8")
    assert "'tip_sounds_enabled': True" in profile_source
    assert "Reproducir un sonido suave" in settings_source
    assert (ROOT / "assets" / "sounds" / "tip.wav").stat().st_size > 1000



def test_tip_bag_does_not_repeat_last_tip_when_refilled():
    class ReverseRng:
        @staticmethod
        def shuffle(values):
            values.reverse()

    last = ASSISTANT_TIPS[-1][0]
    tip, remaining = take_assistant_tip([], last, rng=ReverseRng())
    assert tip[0] != last
    assert len(remaining) == len(ASSISTANT_TIPS) - 1
    seen = {tip[0]}
    while remaining:
        tip, remaining = take_assistant_tip(remaining, tip[0], rng=ReverseRng())
        assert tip[0] not in seen
        seen.add(tip[0])
    assert len(seen) == len(ASSISTANT_TIPS)

def test_manual_rumble_has_priority_and_replays_until_stop():
    manager = ConnectionManager()
    controller = _FakeController()
    manager.dualsense = controller
    manager._connected = True

    assert manager.set_rumble(999, -20)
    assert (controller.leftMotor, controller.rightMotor) == (255, 0)

    assert manager.start_rumble_test(90, 140, duration_ms=120)
    assert manager.set_rumble(1, 2, source="game") is False
    assert (controller.leftMotor, controller.rightMotor) == (90, 140)
    time.sleep(0.21)
    assert (controller.leftMotor, controller.rightMotor) == (0, 0)
    diagnostics = manager.get_rumble_diagnostics()
    assert diagnostics["writes"] >= 4
    assert diagnostics["errors"] == 0
    assert diagnostics["manual_test_active"] is False


def test_update_manifest_check_download_and_hash(tmp_path: Path):
    installer_bytes = b"Nikaido installer test payload"
    digest = hashlib.sha256(installer_bytes).hexdigest()
    manifest = {
        "product": "Nikaido DualSense",
        "channel": "beta",
        "version": "2.9.9.0",
        "title": "Nikaido Beta",
        "notes": "Prueba",
        "download_url": "https://updates.example.test/Nikaido-Setup.exe",
        "sha256": digest,
        "size_bytes": len(installer_bytes),
    }
    manifest_bytes = json.dumps(manifest).encode("utf-8")
    responses = iter((_Response(manifest_bytes), _Response(installer_bytes)))

    class Profile:
        values = {
            "updates.channel": "beta",
            "updates.manifest_url": "https://updates.example.test/manifest.json",
        }

        def get_setting(self, key, default=None):
            return self.values.get(key, default)

        def set_setting(self, key, value):
            self.values[key] = value

    manager = UpdateManager(Profile(), opener=lambda *_args, **_kwargs: next(responses))
    result = manager.check()
    assert result.available
    assert result.update is not None
    target = manager.download(result.update, destination_dir=tmp_path)
    assert target.read_bytes() == installer_bytes
    assert target.suffix == ".exe"


def test_update_parser_and_version_comparison():
    assert is_newer_version("2.9.7.1", "2.9.7.0")
    assert not is_newer_version("2.9.7.0-beta1", "2.9.7.0")
    payload = {
        "product": "Nikaido DualSense",
        "channel": "stable",
        "version": "3.0.0",
        "download_url": "https://example.test/setup.exe",
        "sha256": "a" * 64,
        "size_bytes": 100,
    }
    parsed = parse_manifest(payload, channel="stable")
    assert isinstance(parsed, UpdateInfo)
    assert parsed.version == "3.0.0"


def test_build_generates_publishable_update_manifest(tmp_path: Path, monkeypatch):
    installer = tmp_path / "Nikaido_DualSense-2.9.8.13-Setup.exe"
    installer.write_bytes(b"installer")
    monkeypatch.setattr(build, "RELEASE_PATH", tmp_path)
    monkeypatch.setenv("NIKAIDO_UPDATE_DOWNLOAD_BASE_URL", "https://downloads.example.test")
    output = build.write_update_manifest(installer)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["version"] == APP_VERSION
    assert payload["channel"] == "beta"
    assert payload["download_url"].endswith(installer.name)
    assert payload["sha256"] == hashlib.sha256(b"installer").hexdigest()


def test_release_privacy_audit_uses_build_environment_without_storing_identity(tmp_path: Path):
    from tools.privacy_audit import audit_paths, collect_sensitive_terms

    terms = collect_sensitive_terms(
        {
            "USERNAME": "PrivateBuildToken",
            "USERPROFILE": r"C:\Users\ExampleUser",
            "HOME": "",
            "USER": "",
        }
    )
    assert "PrivateBuildToken" in terms
    leaked = tmp_path / "leaked.bin"
    leaked.write_bytes(b"debug PrivateBuildToken project main.py")
    findings = audit_paths([leaked], terms=terms)
    assert findings
    assert any(item.kind == "término privado" for item in findings)

    placeholder = tmp_path / "placeholder.txt"
    placeholder.write_text(r"C:\Users\ExampleUser\project", encoding="utf-8")
    assert audit_paths([placeholder], terms=()) == []


def test_build_pipeline_blocks_private_release_data():
    normal = (ROOT / "build.py").read_text(encoding="utf-8")
    protected = (ROOT / "build_protected.py").read_text(encoding="utf-8")
    assert "require_private_release([privacy_target, *helpers])" in normal
    assert "require_private_release([zip_path])" in normal
    assert "require_private_release([privacy_target, *helpers, manifest])" in protected
    assert "require_private_release([zip_path])" in protected
