import json
import zipfile
from pathlib import Path

import build_protected
from tools.privacy_audit import (
    audit_paths,
    audit_paths_detailed,
    collect_sensitive_terms,
    write_audit_report,
)


def _windows_user_path(username: str, tail: str = "") -> str:
    # Se construye por partes para que el propio archivo de pruebas no parezca
    # una filtración al auditar el ZIP de código fuente.
    base = "C:" + "\\Users\\" + username
    return base + (("\\" + tail.lstrip("\\")) if tail else "")


def _path_bytes(username: str, tail: str = "") -> bytes:
    return _windows_user_path(username, tail).encode("ascii")


def _terms():
    return collect_sensitive_terms(
        {
            "USERNAME": "PrivateBuildToken",
            "USERPROFILE": _windows_user_path("PrivateBuildToken"),
            "USER": "",
            "HOME": "",
            "COMPUTERNAME": "NIKAIDO-BUILD-BOX",
        }
    )


def test_foreign_native_builder_path_is_warning_not_blocker(tmp_path: Path):
    dll = tmp_path / "PySide6" / "qt-plugins" / "platforms" / "qwindows.dll"
    dll.parent.mkdir(parents=True)
    dll.write_bytes(b"debug metadata " + _path_bytes("DependencyBuilder", r"work\qtbase\src"))

    report = audit_paths_detailed([tmp_path], terms=_terms())
    assert report.passed
    assert not report.errors
    assert report.warnings
    assert report.warnings[0].severity == "warning"
    assert report.warnings[0].origin == "third_party"
    assert audit_paths([tmp_path], terms=_terms()) == []


def test_current_builder_identity_inside_native_binary_still_blocks(tmp_path: Path):
    dll = tmp_path / "PySide6" / "qt6core.dll"
    dll.parent.mkdir(parents=True)
    dll.write_bytes(b"debug metadata " + _path_bytes("PrivateBuildToken", "project"))

    report = audit_paths_detailed([tmp_path], terms=_terms())
    assert not report.passed
    assert any(item.severity == "error" for item in report.findings)
    assert any(item.kind == "término privado" for item in report.errors)


def test_user_path_in_owned_text_file_blocks_even_when_username_is_foreign(tmp_path: Path):
    leaked = tmp_path / "runtime-config.json"
    leaked.write_text(json.dumps({"source": _windows_user_path("ForeignBuilder", "project")}), encoding="utf-8")

    report = audit_paths_detailed([tmp_path], terms=_terms())
    assert not report.passed
    assert any("archivo distribuido" in item.kind for item in report.errors)


def test_strict_mode_can_block_foreign_native_metadata(tmp_path: Path):
    dll = tmp_path / "vgamepad" / "win" / "ViGEmClient.dll"
    dll.parent.mkdir(parents=True)
    dll.write_bytes(b"PDB " + _path_bytes("DependencyBuilder", r"source\vigem"))

    report = audit_paths_detailed(
        [tmp_path], terms=_terms(), strict_third_party=True
    )
    assert not report.passed
    assert report.errors


def test_zip_members_are_classified_without_exposing_absolute_build_path(tmp_path: Path):
    archive_path = tmp_path / "Nikaido-release.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "Nikaido/PySide6/qt-plugins/platforms/qwindows.dll",
            b"PDB " + _path_bytes("DependencyBuilder", "qtbase"),
        )

    report = audit_paths_detailed([archive_path], terms=_terms())
    assert report.passed
    assert report.warnings
    assert all(str(tmp_path) not in item.file for item in report.findings)
    assert report.warnings[0].file.startswith("Nikaido-release.zip!")


def test_distributable_report_redacts_values_and_uses_relative_labels(tmp_path: Path):
    leaked = tmp_path / "Nikaido" / "settings.json"
    leaked.parent.mkdir(parents=True)
    leaked.write_text(
        json.dumps({"build": _windows_user_path("PrivateBuildToken", "project")}),
        encoding="utf-8",
    )
    report = audit_paths_detailed([leaked.parent], terms=_terms())
    output = write_audit_report(report, tmp_path / "PRIVACY_AUDIT.json")
    raw = output.read_text(encoding="utf-8")
    payload = json.loads(raw)

    assert payload["schema_version"] == 2
    assert payload["result"] == "blocked"
    assert payload["policy"]["values_redacted"] is True
    assert "PrivateBuildToken" not in raw
    assert str(tmp_path) not in raw
    assert all(item["value"] == "<redacted>" for item in payload["findings"])


def test_protected_build_excludes_comtypes_tests_and_test_data(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(build_protected, "BUILD_ROOT", tmp_path / "work")
    monkeypatch.setattr(build_protected, "ENTRY_ROOT", tmp_path / "work" / "entry")
    monkeypatch.setattr(build_protected, "NUITKA_OUTPUT", tmp_path / "work" / "nuitka")
    monkeypatch.setattr(
        build_protected, "REPORT_PATH", tmp_path / "work" / "report.xml"
    )
    command = build_protected.build_command(
        onefile=False, console=False, jobs=2
    )
    joined = "\n".join(command)
    assert "--nofollow-import-to=comtypes.test" in joined
    assert "--noinclude-data-files=comtypes/test/**" in joined
    assert "--noinclude-unittest-mode=nofollow" in joined
    assert "--noinclude-doctest-mode" not in joined


def test_many_third_party_warnings_cannot_hide_later_private_error(tmp_path: Path):
    third_party = tmp_path / "PySide6" / "qt-plugins"
    third_party.mkdir(parents=True)
    for index in range(100):
        (third_party / f"plugin_{index:03d}.dll").write_bytes(
            b"PDB " + _path_bytes(f"external{index:03d}", r"qt\source")
        )
    leaked = tmp_path / "zz-final-private.json"
    leaked.write_text(
        json.dumps({"path": _windows_user_path("PrivateBuildToken", "Nikaido")}),
        encoding="utf-8",
    )

    report = audit_paths_detailed([tmp_path], terms=_terms())
    assert not report.passed
    assert report.errors
    assert len(report.warnings) <= 80
    assert any(item.file.endswith("zz-final-private.json") for item in report.errors)


def test_compressed_media_does_not_block_on_random_short_term_bytes(tmp_path: Path):
    image = tmp_path / "avatar.png"
    short_term = "o" + "ai"
    image.write_bytes(b"\x89PNG\r\n\x1a\ncompressed-" + short_term.encode("ascii") + b"-pixel-stream")

    report = audit_paths_detailed([tmp_path], terms=(short_term,))
    assert report.passed
    assert not report.errors


def test_owned_data_file_still_blocks_when_it_contains_a_user_path(tmp_path: Path):
    image = tmp_path / "metadata.png"
    image.write_bytes(b"PNG metadata " + _path_bytes("PrivateBuildToken", "avatar"))

    report = audit_paths_detailed([tmp_path], terms=_terms())
    assert not report.passed
    assert any("ruta privada" in item.kind or "término privado" in item.kind for item in report.errors)
