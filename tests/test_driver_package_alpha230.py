"""Regresiones portables del paquete sin firma de Alpha 2.3.0."""

from __future__ import annotations

import json
import os
import shutil
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from native.vhf.tools import package_driver
from native.vhf.tools.package_driver import (
    BUILD_RECORD_NAME,
    BUILD_RECORD_SCHEMA_VERSION,
    CATALOG_NAME,
    DRIVER_NAME,
    EXIT_ARTIFACT_INVALID,
    EXIT_BUILD_RECORD_INVALID,
    EXIT_INF2CAT_MISSING,
    EXIT_INFVERIF_FAILED,
    EXIT_INFVERIF_MISSING,
    IMAGE_FILE_EXECUTABLE_IMAGE,
    IMAGE_FILE_MACHINE_AMD64,
    IMAGE_FILE_SYSTEM,
    IMAGE_NT_OPTIONAL_HDR64_MAGIC,
    IMAGE_SUBSYSTEM_NATIVE,
    INF2CAT_TARGETS,
    INF_NAME,
    PACKAGE_DIRECTORY_NAME,
    PACKAGE_MANIFEST_NAME,
    PDB_NAME,
    PackagePreparationError,
    PackageToolReport,
    ToolExecution,
    ToolResolution,
    clear_build_record,
    evaluate_compatible_inf2cat,
    evaluate_package_tools,
    inspect_package_tools,
    inspect_pe_driver,
    prepare_package,
    record_successful_build,
    sanitize_tool_output,
    validate_source_inf,
)


ROOT = Path(__file__).resolve().parents[1]
VHF = ROOT / "native" / "vhf"


def _touch(path: Path, payload: bytes = b"fixture") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _write_pe_driver(
    path: Path,
    *,
    machine: int = IMAGE_FILE_MACHINE_AMD64,
    number_of_sections: int = 1,
    characteristics: int = IMAGE_FILE_EXECUTABLE_IMAGE | 0x0020 | 0x2000,
    subsystem: int = IMAGE_SUBSYSTEM_NATIVE,
    address_of_entry_point: int = 0x1000,
    certificate_size: int = 0,
) -> Path:
    payload = bytearray(512)
    payload[:2] = b"MZ"
    pe_offset = 0x80
    struct.pack_into("<I", payload, 0x3C, pe_offset)
    payload[pe_offset : pe_offset + 4] = b"PE\0\0"
    optional_size = 0xF0
    struct.pack_into(
        "<HHIIIHH",
        payload,
        pe_offset + 4,
        machine,
        number_of_sections,
        0,
        0,
        0,
        optional_size,
        characteristics,
    )
    optional_offset = pe_offset + 24
    struct.pack_into("<H", payload, optional_offset, IMAGE_NT_OPTIONAL_HDR64_MAGIC)
    struct.pack_into("<I", payload, optional_offset + 16, address_of_entry_point)
    struct.pack_into("<H", payload, optional_offset + 68, subsystem)
    struct.pack_into("<I", payload, optional_offset + 108, 16)
    struct.pack_into("<II", payload, optional_offset + 112 + 32, 0, certificate_size)
    return _touch(path, bytes(payload))


def _tools(
    tmp_path: Path,
    *,
    infverif: bool = True,
    inf2cat: bool = True,
    inf2cat_kit_version: str = "10.0.28000.0",
) -> PackageToolReport:
    infverif_path = _touch(tmp_path / "tools" / "InfVerif.exe") if infverif else None
    inf2cat_path = _touch(tmp_path / "tools" / "Inf2Cat.exe") if inf2cat else None
    return PackageToolReport(
        toolchain_ready=True,
        selected_kit_version="10.0.28000.0",
        infverif=ToolResolution(
            "InfVerif.exe",
            infverif_path,
            "Tools/x64" if infverif else "",
            "x64" if infverif else None,
            "10.0.28000.0" if infverif else None,
        ),
        inf2cat=ToolResolution(
            "Inf2Cat.exe",
            inf2cat_path,
            "bin/<kit>/x64" if inf2cat else "",
            "x64" if inf2cat else None,
            inf2cat_kit_version if inf2cat else None,
        ),
    )


def _project_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    driver_dir = root / "native" / "vhf" / "driver"
    shared_dir = root / "native" / "vhf" / "shared"
    _touch(driver_dir / "driver.c", b"source")
    _touch(driver_dir / "NikaidoVirtualHid.vcxproj", b"project")
    _touch(shared_dir / "nikaido_vhf_protocol.h", b"protocol")
    shutil.copy2(VHF / "driver" / INF_NAME, driver_dir / INF_NAME)
    built = _write_pe_driver(driver_dir / "x64" / "Release" / DRIVER_NAME)
    symbols = _touch(driver_dir / "x64" / "Release" / PDB_NAME, b"portable-pdb-fixture")
    newest_source = max(
        path.stat().st_mtime_ns
        for path in (
            driver_dir / "driver.c",
            driver_dir / "NikaidoVirtualHid.vcxproj",
            shared_dir / "nikaido_vhf_protocol.h",
            driver_dir / INF_NAME,
        )
    )
    os.utime(built, ns=(newest_source + 1_000_000, newest_source + 1_000_000))
    os.utime(symbols, ns=(newest_source + 1_000_000, newest_source + 1_000_000))
    record_successful_build(root)
    return root


def test_alpha230_metadata_records_the_verified_windows_evidence() -> None:
    metadata = json.loads((ROOT / "VIRTUAL_DUALSENSE_LAB_PROJECT.json").read_text("utf-8"))
    assert metadata["version"] == "3.0.0-alpha.2.3.0"
    assert metadata["lab_name"] == "Microsoft Signing Readiness"
    assert metadata["alpha221_base_sha256"] == (
        "f9148decb8c23e83f13563a456ecc518f703194602197b4ca5f0e0e72eccc9e6"
    )
    assert metadata["alpha222_base_sha256"] == (
        "56cb9ad6d910d4d21e85ddf9cc07303ff01005221dce2676f966975c8ce9b937"
    )
    assert metadata["alpha215_base_sha256"] == (
        "57eee739ab9069ccb950f5895116f41c4f75efc887cf7d5821efb2558bb1b292"
    )
    evidence = metadata["alpha215_windows_evidence"]
    assert evidence["compiler_warnings"] == 0
    assert evidence["compiler_errors"] == 0
    assert evidence["client_reported_win32_error"] == 259
    assert evidence["client_status_exit_code"] == 3
    assert evidence["client_unicode_output_correct"] is True
    assert evidence["driver_installed_or_loaded"] is False
    alpha22 = metadata["alpha22_windows_evidence"]
    assert alpha22["build_kit_version"] == "10.0.28000.0"
    assert alpha22["compatible_inf2cat_discovered_version"] == "10.0.26100.0"
    assert alpha22["compatible_inf2cat_architecture"] == "x86"
    assert alpha22["package_generated"] is False
    alpha221 = metadata["alpha221_windows_evidence"]
    assert alpha221["driver_and_client_built"] is True
    assert alpha221["compiler_warnings"] == 0
    assert alpha221["compiler_errors"] == 0
    assert alpha221["freshness_gate_false_positive_after_successful_build"] is True
    assert alpha221["package_generated"] is False
    alpha222 = metadata["alpha222_windows_evidence"]
    assert alpha222["driver_and_client_built"] is True
    assert alpha222["compiler_warnings"] == 0
    assert alpha222["compiler_errors"] == 0
    assert alpha222["pe_system_characteristic_absent"] is True
    assert alpha222["local_pe_gate_false_positive_after_successful_wdk_build"] is True
    assert alpha222["build_record_created"] is False
    assert alpha222["infverif_executed"] is False
    assert alpha222["inf2cat_executed"] is False
    assert alpha222["package_generated"] is False
    alpha223 = metadata["alpha223_windows_evidence"]
    assert alpha223["driver_and_client_built"] is True
    assert alpha223["compiler_warnings"] == 0
    assert alpha223["compiler_errors"] == 0
    assert alpha223["infverif_universal_passed"] is True
    assert alpha223["inf2cat_passed"] is True
    assert alpha223["catalog_generated"] is True
    assert alpha223["catalog_signed"] is False
    assert alpha223["driver_installed_or_loaded"] is False


def test_same_kit_tools_prefer_versioned_x64_and_fall_back_to_x86(tmp_path: Path) -> None:
    kit = tmp_path / "kit"
    version = "10.0.28000.0"
    _touch(kit / "Tools" / version / "x64" / "InfVerif.exe")
    _touch(kit / "bin" / version / "x86" / "Inf2Cat.exe")
    infverif, inf2cat = evaluate_package_tools(kit, version)
    assert infverif.available is True
    assert infverif.architecture == "x64"
    assert infverif.location == "Tools/<kit>/x64"
    assert infverif.kit_version == version
    assert inf2cat.available is True
    assert inf2cat.architecture == "x86"
    assert inf2cat.location == "bin/<kit>/x86"
    assert inf2cat.kit_version == version
    serialized = json.dumps([infverif.to_dict(), inf2cat.to_dict()])
    assert str(tmp_path) not in serialized


def test_compatible_inf2cat_uses_same_windows_kits_root_and_ignores_old_builds(
    tmp_path: Path,
) -> None:
    kit = tmp_path / "kit"
    _touch(kit / "bin" / "10.0.22621.0" / "x64" / "Inf2Cat.exe")
    expected = _touch(kit / "bin" / "10.0.26100.0" / "x86" / "Inf2Cat.exe")

    result = evaluate_compatible_inf2cat(kit, "10.0.28000.0")

    assert result.path == expected
    assert result.architecture == "x86"
    assert result.kit_version == "10.0.26100.0"
    assert result.location == "bin/<compatible-kit>/x86"
    serialized = json.dumps(result.to_dict())
    assert str(tmp_path) not in serialized


def test_package_inspection_prefers_inf2cat_from_selected_build_kit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = "10.0.28000.0"
    kit = tmp_path / "kit"
    (kit / "Include" / version).mkdir(parents=True)
    _touch(kit / "Tools" / version / "x64" / "InfVerif.exe")
    expected = _touch(kit / "bin" / version / "x86" / "Inf2Cat.exe")
    _touch(kit / "bin" / "10.0.30000.0" / "x64" / "Inf2Cat.exe")
    monkeypatch.setattr(
        package_driver,
        "inspect_installed_toolchain",
        lambda _environment: SimpleNamespace(
            ready=True,
            selected_kit_version=version,
        ),
    )

    report = inspect_package_tools({"WDKContentRoot": str(kit)})

    assert report.ready is True
    assert report.inf2cat.path == expected
    assert report.inf2cat.kit_version == version
    assert report.inf2cat.location == "bin/<kit>/x86"


def test_package_inspection_falls_back_to_user_reported_26100_x86_layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = "10.0.28000.0"
    program_files_x86 = tmp_path / "Program Files (x86)"
    kit = program_files_x86 / "Windows Kits" / "10"
    (kit / "Include" / version).mkdir(parents=True)
    _touch(kit / "Tools" / version / "x64" / "InfVerif.exe")
    expected = _touch(kit / "bin" / "10.0.26100.0" / "x86" / "Inf2Cat.exe")
    monkeypatch.setattr(
        package_driver,
        "inspect_installed_toolchain",
        lambda _environment: SimpleNamespace(
            ready=True,
            selected_kit_version=version,
        ),
    )

    report = inspect_package_tools({"ProgramFiles(x86)": str(program_files_x86)})

    assert report.ready is True
    assert report.selected_kit_version == version
    assert report.infverif.kit_version == version
    assert report.inf2cat.path == expected
    assert report.inf2cat.kit_version == "10.0.26100.0"
    assert report.inf2cat.architecture == "x86"
    assert report.to_dict()["build_kit_version"] == version
    assert str(tmp_path) not in json.dumps(report.to_dict())


def test_missing_package_tools_have_distinct_exit_codes(tmp_path: Path) -> None:
    assert _tools(tmp_path / "a", infverif=False).exit_code == EXIT_INFVERIF_MISSING
    assert _tools(tmp_path / "b", inf2cat=False).exit_code == EXIT_INF2CAT_MISSING


def test_pe_gate_accepts_real_wdk_shape_without_system_characteristic(
    tmp_path: Path,
) -> None:
    wdk_driver = _write_pe_driver(tmp_path / "wdk.sys")
    inspection = inspect_pe_driver(wdk_driver)
    assert inspection.valid_unsigned_x64_driver is True
    assert inspection.system_characteristic_present is False
    assert inspection.address_of_entry_point == 0x1000
    assert inspection.number_of_sections == 1

    with_system_bit = _write_pe_driver(
        tmp_path / "system-bit.sys",
        characteristics=IMAGE_FILE_EXECUTABLE_IMAGE | IMAGE_FILE_SYSTEM,
    )
    assert inspect_pe_driver(with_system_bit).valid_unsigned_x64_driver is True

    signed = _write_pe_driver(tmp_path / "signed.sys", certificate_size=128)
    with pytest.raises(PackagePreparationError) as signed_error:
        inspect_pe_driver(signed)
    assert signed_error.value.exit_code == EXIT_ARTIFACT_INVALID
    assert "firma incrustada" in str(signed_error.value)

    x86 = _write_pe_driver(tmp_path / "x86.sys", machine=0x014C)
    with pytest.raises(PackagePreparationError, match="arquitectura distinta de x64"):
        inspect_pe_driver(x86)

    not_executable = _write_pe_driver(
        tmp_path / "not-executable.sys",
        characteristics=0x0020 | 0x2000,
    )
    with pytest.raises(PackagePreparationError, match="imagen ejecutable"):
        inspect_pe_driver(not_executable)

    no_entry_point = _write_pe_driver(
        tmp_path / "no-entry.sys",
        address_of_entry_point=0,
    )
    with pytest.raises(PackagePreparationError, match="punto de entrada"):
        inspect_pe_driver(no_entry_point)

    no_sections = _write_pe_driver(
        tmp_path / "no-sections.sys",
        number_of_sections=0,
    )
    with pytest.raises(PackagePreparationError, match="no contiene secciones"):
        inspect_pe_driver(no_sections)


def test_alpha230_source_inf_passes_local_identity_gate() -> None:
    validate_source_inf(VHF / "driver" / INF_NAME)
    source = (VHF / "driver" / INF_NAME).read_text("utf-8")
    assert "DriverVer=07/23/2026,3.0.0.230" in source
    assert 'Publisher="Team Nikaido"' in source
    assert "CatalogFile=NikaidoVirtualHid.cat" in source


def test_hash_record_ignores_future_source_timestamps(tmp_path: Path) -> None:
    project = _project_fixture(tmp_path)
    driver_dir = project / "native" / "vhf" / "driver"
    shared_dir = project / "native" / "vhf" / "shared"
    future = 4_102_444_800_000_000_000
    for source in (
        driver_dir / "driver.c",
        driver_dir / "NikaidoVirtualHid.vcxproj",
        driver_dir / INF_NAME,
        shared_dir / "nikaido_vhf_protocol.h",
    ):
        os.utime(source, ns=(future, future))
    tools = _tools(tmp_path / "wdk")

    def runner(command, private_values):
        del private_values
        if Path(command[0]).name.casefold() == "inf2cat.exe":
            package_argument = next(item for item in command if item.casefold().startswith("/driver:"))
            package_dir = Path(package_argument.split(":", 1)[1])
            _touch(package_dir / CATALOG_NAME, b"unsigned-catalog")
        return ToolExecution(0, "validated")

    manifest = prepare_package(project, tools, runner=runner)

    assert manifest["validation"]["build_freshness"] == "verified_by_hash_record"
    assert (
        manifest["validation"]["build_record_schema_version"]
        == BUILD_RECORD_SCHEMA_VERSION
    )


def test_missing_build_record_blocks_package_without_running_tools(tmp_path: Path) -> None:
    project = _project_fixture(tmp_path)
    assert clear_build_record(project) is True
    tools = _tools(tmp_path / "wdk")
    calls = []

    with pytest.raises(PackagePreparationError) as failure:
        prepare_package(
            project,
            tools,
            runner=lambda command, private_values: calls.append((command, private_values)),
        )

    assert failure.value.exit_code == EXIT_BUILD_RECORD_INVALID
    assert "registro de compilación" in str(failure.value)
    assert calls == []


def test_changed_source_after_build_record_is_rejected(tmp_path: Path) -> None:
    project = _project_fixture(tmp_path)
    source = project / "native" / "vhf" / "driver" / "driver.c"
    source.write_bytes(source.read_bytes() + b"\nchanged")

    with pytest.raises(PackagePreparationError) as failure:
        prepare_package(project, _tools(tmp_path / "wdk"))

    assert failure.value.exit_code == EXIT_BUILD_RECORD_INVALID
    assert "fuente cambió" in str(failure.value)


def test_changed_driver_after_build_record_is_rejected(tmp_path: Path) -> None:
    project = _project_fixture(tmp_path)
    driver = project / "native" / "vhf" / "driver" / "x64" / "Release" / DRIVER_NAME
    payload = bytearray(driver.read_bytes())
    payload[-1] ^= 0x01
    driver.write_bytes(payload)

    with pytest.raises(PackagePreparationError) as failure:
        prepare_package(project, _tools(tmp_path / "wdk"))

    assert failure.value.exit_code == EXIT_BUILD_RECORD_INVALID
    assert "driver cambió" in str(failure.value)


def test_changed_pdb_after_build_record_is_rejected(tmp_path: Path) -> None:
    project = _project_fixture(tmp_path)
    symbols = project / "native" / "vhf" / "driver" / "x64" / "Release" / PDB_NAME
    symbols.write_bytes(symbols.read_bytes() + b"-changed")

    with pytest.raises(PackagePreparationError) as failure:
        prepare_package(project, _tools(tmp_path / "wdk"))

    assert failure.value.exit_code == EXIT_BUILD_RECORD_INVALID
    assert "PDB cambió" in str(failure.value)


def test_build_record_is_relative_sanitized_and_safely_clearable(tmp_path: Path) -> None:
    project = _project_fixture(tmp_path)
    release = project / "native" / "vhf" / "driver" / "x64" / "Release"
    record = release / BUILD_RECORD_NAME
    driver = release / DRIVER_NAME
    source = project / "native" / "vhf" / "driver" / "driver.c"
    payload = json.loads(record.read_text("utf-8"))
    serialized = json.dumps(payload)

    assert str(tmp_path) not in serialized
    assert payload["status"] == "successful"
    assert len(payload["inputs"]) == 4
    assert payload["output"]["path"].endswith(DRIVER_NAME)
    assert payload["symbols"]["path"].endswith(PDB_NAME)
    assert payload["schema_version"] == BUILD_RECORD_SCHEMA_VERSION
    assert payload["pe_validation"]["executable_image"] is True
    assert payload["pe_validation"]["entry_point_present"] is True
    assert payload["pe_validation"]["system_characteristic_present"] is False
    assert payload["pe_validation"]["embedded_certificate_present"] is False
    assert clear_build_record(project) is True
    assert not record.exists()
    assert driver.is_file()
    assert source.is_file()
    assert clear_build_record(project) is False


def test_tool_output_sanitizer_removes_user_host_and_project_paths() -> None:
    separator = "\\"
    synthetic_user_path = separator.join(("C:", "Users", "PrivateName", "Downloads", "Lab"))
    raw = (
        f"{synthetic_user_path}{separator}driver.inf\n"
        "host-private C:/workspace/private/Lab"
    )
    clean = sanitize_tool_output(
        raw,
        ("PrivateName", "host-private", "C:/workspace/private/Lab"),
    )
    assert "PrivateName" not in clean
    assert "host-private" not in clean
    assert "workspace/private" not in clean
    assert "<PRIVATE>" in clean


def test_prepare_package_is_transactional_and_manifested(tmp_path: Path) -> None:
    project = _project_fixture(tmp_path)
    tools = _tools(
        tmp_path / "wdk",
        inf2cat_kit_version="10.0.26100.0",
    )
    commands: list[tuple[str, ...]] = []

    def runner(command, private_values):
        del private_values
        commands.append(tuple(command))
        if Path(command[0]).name.casefold() == "inf2cat.exe":
            package_argument = next(item for item in command if item.casefold().startswith("/driver:"))
            package_dir = Path(package_argument.split(":", 1)[1])
            _touch(package_dir / CATALOG_NAME, b"unsigned-catalog")
        return ToolExecution(0, "validated <PRIVATE>")

    manifest = prepare_package(project, tools, runner=runner)
    output = project / "native" / "vhf" / "out"
    package = output / PACKAGE_DIRECTORY_NAME
    manifest_path = output / PACKAGE_MANIFEST_NAME
    assert sorted(path.name for path in package.iterdir()) == [
        CATALOG_NAME,
        INF_NAME,
        DRIVER_NAME,
    ]
    assert not (output / f"{PACKAGE_DIRECTORY_NAME}.staging").exists()
    assert manifest_path.is_file()
    assert manifest["validation"]["infverif_universal"] == "passed"
    assert manifest["validation"]["catalog_signature"] == "absent_by_design"
    assert manifest["validation"]["build_freshness"] == "verified_by_hash_record"
    assert (
        manifest["validation"]["build_record_schema_version"]
        == BUILD_RECORD_SCHEMA_VERSION
    )
    assert manifest["validation"]["pe_executable_image"] == "passed"
    assert manifest["validation"]["pe_entry_point"] == "present"
    assert (
        manifest["validation"]["pe_system_characteristic"]
        == "informational_not_required"
    )
    assert manifest["validation"]["kit_version"] == "10.0.28000.0"
    assert manifest["validation"]["build_kit_version"] == "10.0.28000.0"
    assert manifest["validation"]["infverif_kit_version"] == "10.0.28000.0"
    assert manifest["validation"]["inf2cat_kit_version"] == "10.0.26100.0"
    assert manifest["validation"]["inf2cat_separate_compatible_kit"] is True
    assert manifest["security"]["driver_installed"] is False
    assert manifest["security"]["driver_signed"] is False
    assert manifest["symbols"]["path"].endswith(PDB_NAME)
    assert len(manifest["files"]) == 3
    serialized = manifest_path.read_text("utf-8")
    assert str(tmp_path) not in serialized
    assert commands[0][1:3] == ("/v", "/u")
    assert f"/os:{','.join(INF2CAT_TARGETS)}" in commands[1]
    assert "/uselocaltime" in commands[1]


def test_failed_infverif_removes_staging_and_never_runs_inf2cat(tmp_path: Path) -> None:
    project = _project_fixture(tmp_path)
    tools = _tools(tmp_path / "wdk")
    commands: list[tuple[str, ...]] = []

    def runner(command, private_values):
        del private_values
        commands.append(tuple(command))
        return ToolExecution(9, "INF rejected")

    with pytest.raises(PackagePreparationError) as failure:
        prepare_package(project, tools, runner=runner)
    assert failure.value.exit_code == EXIT_INFVERIF_FAILED
    output = project / "native" / "vhf" / "out"
    assert not (output / f"{PACKAGE_DIRECTORY_NAME}.staging").exists()
    assert not (output / PACKAGE_DIRECTORY_NAME).exists()
    assert len(commands) == 1


def test_package_scripts_never_install_sign_or_weaken_windows() -> None:
    paths = (
        ROOT / "BUILD_VHF_ALPHA230.bat",
        ROOT / "CHECK_VHF_ALPHA230_SIGNING_READINESS.bat",
        ROOT / "PREPARE_VHF_ALPHA230_PACKAGE.bat",
        VHF / "tools" / "RUN_VHF_PACKAGE_TOOL.bat",
        VHF / "tools" / "package_driver.py",
    )
    source = "\n".join(path.read_text("utf-8-sig").casefold() for path in paths)
    forbidden_commands = (
        "pnputil ",
        "devcon ",
        "bcdedit ",
        "sc create",
        "signtool ",
        "runas ",
        "powershell start-process",
    )
    assert not any(command in source for command in forbidden_commands)
    assert "infverif" in source
    assert "inf2cat" in source
    assert "<enableinf2cat>false</enableinf2cat>" in (
        VHF / "driver" / "NikaidoVirtualHid.vcxproj"
    ).read_text("utf-8").casefold()


def test_source_distribution_has_no_generated_package_directory() -> None:
    assert not (VHF / "out").exists()
    assert not any(ROOT.rglob(BUILD_RECORD_NAME))
