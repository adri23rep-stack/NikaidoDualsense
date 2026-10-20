"""Regresiones portables de preparación y verificación de firma Alpha 2.3.0."""

from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from native.vhf.tools import signing_readiness
from native.vhf.tools.package_driver import (
    BUILD_RECORD_SCHEMA_VERSION,
    CATALOG_NAME,
    DRIVER_NAME,
    INF_NAME,
    PACKAGE_DIRECTORY_NAME,
    PACKAGE_MANIFEST_NAME,
    PDB_NAME,
    PRODUCT,
    PUBLISHER,
    VERSION,
    ToolExecution,
    ToolResolution,
)
from native.vhf.tools.signing_readiness import (
    EXIT_PRIVACY,
    EXIT_RETURN_INVALID,
    SUBMISSION_CAB_NAME,
    SUBMISSION_DRIVER_FOLDER,
    SUBMISSION_MANIFEST_NAME,
    SigningReadinessError,
    SigningToolReport,
    assert_no_private_markers,
    create_submission_cab,
    inspect_pe_payload,
    inspect_signing_tools,
    private_markers,
    read_cab_file_names,
    validate_unsigned_package,
    verify_microsoft_return,
    write_submission_ddf,
)


ROOT = Path(__file__).resolve().parents[1]
VHF = ROOT / "native" / "vhf"


def _touch(path: Path, payload: bytes = b"fixture") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(path: Path, name: str) -> dict[str, object]:
    return {
        "path": name,
        "size": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _write_pe(path: Path, *, signed: bool = False, mutate_section: bool = False) -> Path:
    payload = bytearray(0x400)
    payload[:2] = b"MZ"
    pe_offset = 0x80
    struct.pack_into("<I", payload, 0x3C, pe_offset)
    payload[pe_offset : pe_offset + 4] = b"PE\0\0"
    optional_size = 0xF0
    struct.pack_into(
        "<HHIIIHH",
        payload,
        pe_offset + 4,
        0x8664,
        1,
        0,
        0,
        0,
        optional_size,
        0x2022,
    )
    optional_offset = pe_offset + 24
    struct.pack_into("<H", payload, optional_offset, 0x20B)
    struct.pack_into("<I", payload, optional_offset + 16, 0x1000)
    struct.pack_into("<I", payload, optional_offset + 60, 0x200)
    struct.pack_into("<H", payload, optional_offset + 68, 1)
    struct.pack_into("<I", payload, optional_offset + 108, 16)
    section_table = optional_offset + optional_size
    payload[section_table : section_table + 8] = b".text\0\0\0"
    struct.pack_into("<I", payload, section_table + 8, 0x180)
    struct.pack_into("<I", payload, section_table + 12, 0x1000)
    struct.pack_into("<I", payload, section_table + 16, 0x200)
    struct.pack_into("<I", payload, section_table + 20, 0x200)
    payload[0x200:0x400] = bytes((index % 251 for index in range(0x200)))
    if mutate_section:
        payload[0x240] ^= 0x01
    if signed:
        certificate = b"\x10\0\0\0\x00\x02\x02\x00FAKESIGN"
        certificate_offset = len(payload)
        payload.extend(certificate)
        struct.pack_into("<I", payload, optional_offset + 64, 0x12345678)
        struct.pack_into(
            "<II",
            payload,
            optional_offset + 112 + 4 * 8,
            certificate_offset,
            len(certificate),
        )
    return _touch(path, bytes(payload))


def _cab_bytes(names: list[str]) -> bytes:
    records = bytearray()
    for name in names:
        encoded = name.encode("ascii")
        records.extend(struct.pack("<IIHHHH", 1, 0, 0, 0, 0, 0))
        records.extend(encoded + b"\0")
    cabinet_size = 36 + len(records)
    header = bytearray(36)
    header[:4] = b"MSCF"
    struct.pack_into("<I", header, 8, cabinet_size)
    struct.pack_into("<I", header, 16, 36)
    header[24] = 3
    header[25] = 1
    struct.pack_into("<H", header, 26, 1)
    struct.pack_into("<H", header, 28, len(names))
    return bytes(header + records)


def _unsigned_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    output = root / "native" / "vhf" / "out"
    package = output / PACKAGE_DIRECTORY_NAME
    package.mkdir(parents=True)
    inf = package / INF_NAME
    inf.write_bytes((VHF / "driver" / INF_NAME).read_bytes())
    driver = _write_pe(package / DRIVER_NAME)
    catalog = _touch(package / CATALOG_NAME, b"unsigned-catalog")
    pdb = _touch(
        root / "native" / "vhf" / "driver" / "x64" / "Release" / PDB_NAME,
        b"portable-symbols-without-private-paths",
    )
    manifest = {
        "schema_version": 2,
        "product": PRODUCT,
        "publisher": PUBLISHER,
        "version": VERSION,
        "package_directory": PACKAGE_DIRECTORY_NAME,
        "files": [
            _record(inf, INF_NAME),
            _record(driver, DRIVER_NAME),
            _record(catalog, CATALOG_NAME),
        ],
        "symbols": _record(
            pdb,
            f"native/vhf/driver/x64/Release/{PDB_NAME}",
        ),
        "validation": {
            "infverif_universal": "passed",
            "inf2cat": "passed",
            "catalog_signature": "absent_by_design",
            "build_record_schema_version": BUILD_RECORD_SCHEMA_VERSION,
        },
        "security": {
            "driver_signed": False,
            "driver_installed": False,
        },
    }
    (output / PACKAGE_MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return root


def _write_submission_manifest_fixture(project: Path) -> None:
    output = project / "native" / "vhf" / "out"
    cab = _touch(
        output / SUBMISSION_CAB_NAME,
        _cab_bytes(
            [
                f"{SUBMISSION_DRIVER_FOLDER}\\{name}"
                for name in (INF_NAME, DRIVER_NAME, PDB_NAME, CATALOG_NAME)
            ]
        ),
    )
    package_manifest = output / PACKAGE_MANIFEST_NAME
    payload = {
        "product": PRODUCT,
        "publisher": PUBLISHER,
        "version": VERSION,
        "cab": _record(cab, SUBMISSION_CAB_NAME),
        "source_package_manifest": _record(
            package_manifest,
            f"native/vhf/out/{PACKAGE_MANIFEST_NAME}",
        ),
        "signing": {
            "cab_signature": "absent_by_design",
            "microsoft_signature": "not_requested",
        },
    }
    (output / SUBMISSION_MANIFEST_NAME).write_text(
        json.dumps(payload) + "\n",
        encoding="utf-8",
    )


def _tools(tmp_path: Path, *, makecab: bool = True, signtool: bool = True) -> SigningToolReport:
    makecab_path = _touch(tmp_path / "tools" / "makecab.exe") if makecab else None
    signtool_path = _touch(tmp_path / "tools" / "signtool.exe") if signtool else None
    return SigningToolReport(
        selected_kit_version="10.0.28000.0",
        makecab=ToolResolution(
            "MakeCab.exe",
            makecab_path,
            "System32" if makecab else "",
            "native" if makecab else None,
        ),
        signtool=ToolResolution(
            "SignTool.exe",
            signtool_path,
            "bin/<kit>/x64" if signtool else "",
            "x64" if signtool else None,
            "10.0.28000.0" if signtool else None,
        ),
    )


def test_alpha230_signing_tool_discovery_does_not_inspect_certificates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    system_root = tmp_path / "Windows"
    _touch(system_root / "System32" / "makecab.exe")
    kit = tmp_path / "Windows Kits" / "10"
    expected = _touch(kit / "bin" / "10.0.28000.0" / "x64" / "signtool.exe")
    monkeypatch.setattr(
        signing_readiness,
        "inspect_package_tools",
        lambda _environment: SimpleNamespace(selected_kit_version="10.0.28000.0"),
    )

    report = inspect_signing_tools(
        {
            "SystemRoot": str(system_root),
            "WDKContentRoot": str(kit),
        }
    )

    assert report.cab_ready is True
    assert report.return_verification_ready is True
    assert report.signtool.path == expected
    serialized = json.dumps(report.to_dict())
    assert str(tmp_path) not in serialized
    assert report.to_dict()["certificate_store_inspected"] is False
    assert report.to_dict()["certificate_or_key_loaded"] is False


def test_unsigned_package_requires_exact_hashes_and_registered_pdb(tmp_path: Path) -> None:
    project = _unsigned_project(tmp_path)
    manifest, files = validate_unsigned_package(project)

    assert manifest["version"] == VERSION
    assert set(files) == {INF_NAME, DRIVER_NAME, CATALOG_NAME, PDB_NAME}

    files[PDB_NAME].write_bytes(b"changed")
    with pytest.raises(SigningReadinessError, match=r"\.pdb.*hash"):
        validate_unsigned_package(project)


def test_private_pdb_marker_blocks_submission(tmp_path: Path) -> None:
    private_profile = "C:" + "\\Users\\" + "PrivateName"
    pdb = _touch(
        tmp_path / PDB_NAME,
        ("symbols " + private_profile + "\\Downloads\\Nikaido\\driver.c").encode(),
    )
    markers = private_markers(
        {
            "USERPROFILE": private_profile,
            "USERNAME": "PrivateName",
            "COMPUTERNAME": "PrivateHost",
        }
    )

    with pytest.raises(SigningReadinessError) as failure:
        assert_no_private_markers({PDB_NAME: pdb}, markers)

    assert failure.value.exit_code == EXIT_PRIVACY
    assert "privada" in str(failure.value)


def test_ddf_uses_short_subfolder_and_all_four_files(tmp_path: Path) -> None:
    files = {
        name: _touch(tmp_path / "source" / name)
        for name in (INF_NAME, DRIVER_NAME, PDB_NAME, CATALOG_NAME)
    }
    ddf = tmp_path / "submission.ddf"
    write_submission_ddf(
        ddf,
        cabinet_output_directory=tmp_path / "output",
        source_files=files,
    )
    text = ddf.read_text("utf-8")

    assert len(SUBMISSION_DRIVER_FOLDER) < 40
    assert re.fullmatch(r"[A-Za-z0-9]+", SUBMISSION_DRIVER_FOLDER)
    assert f".Set DestinationDir={SUBMISSION_DRIVER_FOLDER}" in text
    assert f".Set CabinetNameTemplate={SUBMISSION_CAB_NAME}" in text
    for name in files:
        assert f'"{name}"' in text


def test_cab_parser_reads_nested_driver_files_and_rejects_invalid_header(
    tmp_path: Path,
) -> None:
    names = [
        f"{SUBMISSION_DRIVER_FOLDER}\\{name}"
        for name in (INF_NAME, DRIVER_NAME, PDB_NAME, CATALOG_NAME)
    ]
    cab = _touch(tmp_path / "valid.cab", _cab_bytes(names))
    assert read_cab_file_names(cab) == tuple(names)

    invalid = _touch(tmp_path / "invalid.cab", b"not-a-cab")
    with pytest.raises(SigningReadinessError, match="MSCF"):
        read_cab_file_names(invalid)


def test_create_submission_is_manifested_private_and_never_signed(tmp_path: Path) -> None:
    project = _unsigned_project(tmp_path)
    tools = _tools(tmp_path / "environment")
    commands: list[tuple[str, ...]] = []
    private_profile = "C:" + "\\Users\\" + "PrivateName"

    def runner(command, private_values):
        del private_values
        commands.append(tuple(command))
        staging = project / "native" / "vhf" / "out" / "NikaidoVhfA230Submission.staging"
        names = [
            f"{SUBMISSION_DRIVER_FOLDER}\\{name}"
            for name in (INF_NAME, DRIVER_NAME, PDB_NAME, CATALOG_NAME)
        ]
        _touch(staging / SUBMISSION_CAB_NAME, _cab_bytes(names))
        return ToolExecution(0, "CAB created at <PRIVATE>")

    manifest = create_submission_cab(
        project,
        tools,
        environment={
            "USERPROFILE": private_profile,
            "USERNAME": "PrivateName",
            "COMPUTERNAME": "PrivateHost",
        },
        runner=runner,
    )
    output = project / "native" / "vhf" / "out"
    manifest_path = output / SUBMISSION_MANIFEST_NAME

    assert (output / SUBMISSION_CAB_NAME).is_file()
    assert manifest_path.is_file()
    assert not (output / "NikaidoVhfA230Submission.staging").exists()
    assert manifest["signing"]["cab_signature"] == "absent_by_design"
    assert manifest["signing"]["ready_for_ev_signature"] is True
    assert manifest["signing"]["ready_for_partner_center_submission"] is False
    assert manifest["cab_structure"]["files_at_root"] == 0
    assert len(manifest["cab_structure"]["files"]) == 4
    serialized = manifest_path.read_text("utf-8")
    assert str(tmp_path) not in serialized
    assert "PrivateName" not in serialized
    assert commands == [
        (
            str(tools.makecab.path),
            "/F",
            str(output / "NikaidoVhfA230Submission.staging" / "NikaidoVhfA230Submission.ddf"),
        )
    ]


def test_pe_payload_digest_ignores_signature_but_detects_section_change(
    tmp_path: Path,
) -> None:
    unsigned = _write_pe(tmp_path / "unsigned.sys")
    signed = _write_pe(tmp_path / "signed.sys", signed=True)
    changed = _write_pe(tmp_path / "changed.sys", signed=True, mutate_section=True)

    unsigned_info = inspect_pe_payload(unsigned)
    signed_info = inspect_pe_payload(signed)
    changed_info = inspect_pe_payload(changed)

    assert unsigned_info.embedded_signature_present is False
    assert signed_info.embedded_signature_present is True
    assert unsigned_info.payload_sha256 == signed_info.payload_sha256
    assert unsigned_info.payload_sha256 != changed_info.payload_sha256


def test_verify_return_checks_kp_membership_and_never_installs(tmp_path: Path) -> None:
    project = _unsigned_project(tmp_path)
    output = project / "native" / "vhf" / "out"
    _write_submission_manifest_fixture(project)
    returned = tmp_path / "returned"
    returned.mkdir()
    (returned / INF_NAME).write_bytes(
        (output / PACKAGE_DIRECTORY_NAME / INF_NAME).read_bytes()
    )
    _write_pe(returned / DRIVER_NAME, signed=True)
    _touch(returned / CATALOG_NAME, b"microsoft-signed-catalog")
    tools = _tools(tmp_path / "environment")
    commands: list[tuple[str, ...]] = []

    def runner(command, private_values):
        del private_values
        commands.append(tuple(command))
        return ToolExecution(0, "Successfully verified: <PRIVATE>")

    result = verify_microsoft_return(project, returned, tools, runner=runner)

    assert result["verification"]["sys_payload_matches_submission"] is True
    assert result["verification"]["sys_embedded_signature"] == "passed_signtool_kp"
    assert len(commands) == 4
    assert all(command[1] == "verify" for command in commands)
    assert all("/kp" in command for command in commands)
    assert not any("sign" == argument.casefold() for command in commands for argument in command)


def test_verify_return_rejects_changed_driver_before_signtool(tmp_path: Path) -> None:
    project = _unsigned_project(tmp_path)
    output = project / "native" / "vhf" / "out"
    _write_submission_manifest_fixture(project)
    returned = tmp_path / "returned"
    returned.mkdir()
    (returned / INF_NAME).write_bytes(
        (output / PACKAGE_DIRECTORY_NAME / INF_NAME).read_bytes()
    )
    _write_pe(returned / DRIVER_NAME, signed=True, mutate_section=True)
    _touch(returned / CATALOG_NAME, b"signed-catalog")
    calls = []

    with pytest.raises(SigningReadinessError) as failure:
        verify_microsoft_return(
            project,
            returned,
            _tools(tmp_path / "environment"),
            runner=lambda command, private_values: calls.append((command, private_values)),
        )

    assert failure.value.exit_code == EXIT_RETURN_INVALID
    assert "secciones" in str(failure.value)
    assert calls == []


def test_alpha230_scripts_never_sign_install_or_weaken_windows() -> None:
    paths = (
        ROOT / "BUILD_VHF_ALPHA230.bat",
        ROOT / "PREPARE_VHF_ALPHA230_PACKAGE.bat",
        ROOT / "CHECK_VHF_ALPHA230_SIGNING_READINESS.bat",
        ROOT / "CREATE_VHF_ALPHA230_SUBMISSION_CAB.bat",
        ROOT / "VERIFY_VHF_ALPHA230_MICROSOFT_RETURN.bat",
        VHF / "tools" / "RUN_VHF_SIGNING_TOOL.bat",
        VHF / "tools" / "signing_readiness.py",
    )
    source = "\n".join(path.read_text("utf-8-sig").casefold() for path in paths)
    forbidden = (
        "pnputil ",
        "devcon ",
        "bcdedit ",
        "sc create",
        "runas ",
        "powershell start-process",
        '"sign",',
        "'sign',",
    )
    assert not any(token in source for token in forbidden)
    assert '"verify",' in source
    assert "makecab" in source
    assert "certificate_store_inspected" in source


def test_source_distribution_contains_no_generated_signing_artifacts() -> None:
    assert not (VHF / "out").exists()
    assert not any(ROOT.rglob("*.cab"))
    assert not any(ROOT.rglob("*.pdb"))
