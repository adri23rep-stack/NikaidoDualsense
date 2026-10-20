"""Validaciones portables heredadas del prototipo fuente KMDF/VHF Alpha 2."""

from __future__ import annotations

import hashlib
import json
import re
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from virtual_dualsense_lab import (
    GENERIC_GAMEPAD_REPORT_DESCRIPTOR,
    LAB_RELEASE,
    LAB_VERSION,
    collect_diagnostics,
)


ROOT = Path(__file__).resolve().parents[1]
VHF = ROOT / "native" / "vhf"
DRIVER = VHF / "driver" / "driver.c"
PROTOCOL = VHF / "shared" / "nikaido_vhf_protocol.h"
INF = VHF / "driver" / "NikaidoVirtualHid.inf"
CLIENT = VHF / "client" / "main.cpp"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _driver_descriptor() -> bytes:
    source = _text(DRIVER)
    match = re.search(
        r"g_NikaidoGamepadReportDescriptor\[\]\s*=\s*\{(?P<body>.*?)\};",
        source,
        flags=re.DOTALL,
    )
    assert match
    body = re.sub(r"/\*.*?\*/", "", match.group("body"), flags=re.DOTALL)
    values = []
    for token in body.split(","):
        token = token.strip()
        if not token:
            continue
        if token == "NIKAIDO_VHF_REPORT_ID":
            values.append(1)
        else:
            values.append(int(token, 0))
    return bytes(values)


def test_alpha2_identity_and_diagnostic_source_state() -> None:
    assert LAB_VERSION == "3.0.0-alpha.2.3.0"
    assert LAB_RELEASE == "Alpha 2.3.0"
    native = collect_diagnostics().to_dict()["native_hid"]
    assert native["driver_source_included"] is True
    assert native["inf_source_included"] is True
    assert native["client_source_included"] is True
    assert native["compiled_driver_included"] is False
    assert native["driver_included"] is False
    assert native["driver_signed"] is False
    assert native["allowed"] is False


def test_diagnostic_checks_the_same_service_name_declared_by_the_inf() -> None:
    diagnostics = _text(ROOT / "virtual_dualsense_lab" / "diagnostics.py")
    inf = _text(INF)
    assert '_service_exists("NikaidoVirtualHid")' in diagnostics
    assert "AddService=NikaidoVirtualHid" in inf


def test_kernel_descriptor_exactly_matches_the_portable_codec() -> None:
    assert _driver_descriptor() == GENERIC_GAMEPAD_REPORT_DESCRIPTOR


def test_shared_binary_contract_has_expected_packed_sizes() -> None:
    protocol = _text(PROTOCOL)
    assert "#pragma pack(push, 1)" in protocol
    assert "NIKAIDO_VHF_PROTOCOL_MAGIC 0x3248564EUL" in protocol
    assert "NIKAIDO_VHF_PROTOCOL_VERSION 1U" in protocol
    assert "NIKAIDO_VHF_INPUT_REPORT_SIZE 16U" in protocol
    assert "NIKAIDO_VHF_WATCHDOG_TIMEOUT_MS 500U" in protocol
    assert "NIKAIDO_VHF_INTERFACE_GUID_COMPONENTS" not in protocol
    assert protocol.count("0x8e44f641") == 1
    assert struct.calcsize("<BHBhhhhHH") == 16
    assert struct.calcsize("<IHHQ16s") == 32
    assert struct.calcsize("<IHHIIQ16s") == 40


def test_driver_uses_the_required_vhf_lifecycle() -> None:
    source = _text(DRIVER)
    for symbol in (
        "VHF_CONFIG_INIT",
        "VhfCreate",
        "VhfStart",
        "VhfReadReportSubmit",
        "VhfDelete",
    ):
        assert symbol in source
    assert "WdfDeviceWdmGetDeviceObject" in source
    assert "VhfDelete(context->VhfHandle, TRUE)" in source
    assert "VhfKm.lib" in _text(VHF / "driver" / "NikaidoVirtualHid.vcxproj")


def test_driver_fails_closed_on_writer_loss_timeout_and_power_transition() -> None:
    source = _text(DRIVER)
    assert "WdfDeviceInitSetExclusive(DeviceInit, TRUE)" in source
    assert "WdfIoQueueDispatchSequential" in source
    assert "NikaidoEvtFileCleanup" in source
    assert "NikaidoEvtWatchdog" in source
    assert "NikaidoEvtDeviceD0Entry" in source
    assert "NikaidoEvtDeviceD0Exit" in source
    assert source.count("NikaidoSubmitNeutral(context)") >= 7
    assert "WDF_TIMER_CONFIG_INIT(&timerConfig, NikaidoEvtWatchdog)" in source
    assert "WDF_TIMER_CONFIG_INIT_PERIODIC" not in source
    assert "WDF_REL_TIMEOUT_IN_MS(NIKAIDO_VHF_WATCHDOG_TIMEOUT_MS)" in source
    assert "timerAttributes.ExecutionLevel = WdfExecutionLevelPassive" in source
    assert "Message->Sequence <= LastSequence" in source
    assert "Report->Buttons & 0xC000U" in source
    assert "Report->Hat > 8U" in source


def test_inf_is_generic_restricted_and_registers_vhf_lower_filter() -> None:
    source = _text(INF)
    compact = source.replace(" ", "")
    assert "Provider=%Publisher%" in source
    assert 'Publisher="Team Nikaido"' in source
    assert "ROOT\\NIKAIDO_VHF_ALPHA2" in source
    assert 'HKR,,"LowerFilters",0x00010000,"vhf"' in compact
    assert 'HKR,,Security,,"D:P(A;;GA;;;SY)(A;;GA;;;BA)"' in compact
    assert "WD;;;" not in source
    assert "IU;;;" not in source
    assert "CatalogFile=NikaidoVirtualHid.cat" in source
    assert "PnpLockdown=1" in source


def test_identity_does_not_claim_a_third_party_vid_or_pid() -> None:
    source = _text(DRIVER)
    assert "vhfConfig.VendorID = 0;" in source
    assert "vhfConfig.ProductID = 0;" in source
    assert "0x054c" not in source.lower()
    assert "0x0ce6" not in source.lower()


def test_client_enumerates_a_device_interface_and_closes_cleanly() -> None:
    source = _text(CLIENT)
    for symbol in (
        "SetupDiGetClassDevsW",
        "SetupDiEnumDeviceInterfaces",
        "SetupDiGetDeviceInterfaceDetailW",
        "CreateFileW",
        "DeviceIoControl",
        "CloseHandle",
    ):
        assert symbol in source
    assert "IOCTL_NIKAIDO_VHF_SUBMIT_INPUT" in source
    assert "IOCTL_NIKAIDO_VHF_NEUTRALIZE" in source
    assert "IOCTL_NIKAIDO_VHF_GET_STATUS" in source


def test_client_preserves_win32_errors_before_setupapi_cleanup() -> None:
    source = _text(CLIENT)
    error_captures = (
        "const DWORD error = NonzeroError(GetLastError(), ERROR_NO_MORE_ITEMS);",
        "const DWORD error = NonzeroError(GetLastError(), ERROR_INVALID_DATA);",
        "const DWORD openError = handle == INVALID_HANDLE_VALUE",
    )
    for statement in error_captures:
        capture = source.index(statement)
        cleanup = source.index("SetupDiDestroyDeviceInfoList(deviceInfo);", capture)
        assert capture < cleanup
    assert "struct OpenLabInterfaceResult" in source
    assert "NonzeroError(GetLastError(), ERROR_GEN_FAILURE)" in source
    assert "NonzeroError(GetLastError(), ERROR_OPEN_FAILED)" in source
    assert "return {INVALID_HANDLE_VALUE, error};" in source
    assert "openResult.error" in source
    assert "error Win32 %lu" in source
    assert "SetLastError(ERROR_INVALID_DATA);" in source


def test_client_writes_unicode_without_depending_on_the_console_code_page() -> None:
    source = _text(CLIENT)
    assert "WriteConsoleW" in source
    assert "WideCharToMultiByte" in source
    assert "CP_UTF8" in source
    assert "WC_ERR_INVALID_CHARS" in source
    assert "std::wprintf" not in source
    assert "std::fwprintf" not in source
    assert 'L"Debe existir un paquete compilado y firmado; la interfaz está restringida.' in source


def test_alpha22_does_not_change_the_alpha214_driver_implementation() -> None:
    assert hashlib.sha256(DRIVER.read_bytes()).hexdigest() == (
        "ca547072b70c12766cceeb570b6c3bbb6e53a51369bc5a1346db9868072f0473"
    )


def test_visual_studio_projects_and_solution_are_structurally_valid() -> None:
    driver_project = VHF / "driver" / "NikaidoVirtualHid.vcxproj"
    client_project = VHF / "client" / "NikaidoVhfClient.vcxproj"
    ET.parse(driver_project)
    ET.parse(client_project)
    driver_xml = _text(driver_project)
    assert "WindowsKernelModeDriver10.0" in driver_xml
    assert "<DriverType>KMDF</DriverType>" in driver_xml
    assert "<SignMode>Off</SignMode>" in driver_xml
    assert "<EnableInf2cat>false</EnableInf2cat>" in driver_xml
    assert "<RunInf2Cat>" not in driver_xml
    solution = _text(VHF / "NikaidoVirtualHid.sln")
    assert "NikaidoVirtualHid.vcxproj" in solution
    assert "NikaidoVhfClient.vcxproj" in solution


def test_build_and_environment_launchers_never_install_or_weaken_windows() -> None:
    sources = "\n".join(
        _text(ROOT / name).lower()
        for name in (
            "BUILD_VHF_ALPHA2.bat",
            "CHECK_VHF_ALPHA2_ENVIRONMENT.bat",
            "BUILD_VHF_ALPHA21.bat",
            "CHECK_VHF_ALPHA21_ENVIRONMENT.bat",
            "BUILD_VHF_ALPHA211.bat",
            "CHECK_VHF_ALPHA211_ENVIRONMENT.bat",
            "BUILD_VHF_ALPHA212.bat",
            "CHECK_VHF_ALPHA212_ENVIRONMENT.bat",
            "BUILD_VHF_ALPHA213.bat",
            "CHECK_VHF_ALPHA213_ENVIRONMENT.bat",
            "BUILD_VHF_ALPHA214.bat",
            "CHECK_VHF_ALPHA214_ENVIRONMENT.bat",
            "BUILD_VHF_ALPHA215.bat",
            "CHECK_VHF_ALPHA215_ENVIRONMENT.bat",
            "BUILD_VHF_ALPHA22.bat",
            "CHECK_VHF_ALPHA22_ENVIRONMENT.bat",
            "PREPARE_VHF_ALPHA22_PACKAGE.bat",
            "BUILD_VHF_ALPHA221.bat",
            "CHECK_VHF_ALPHA221_ENVIRONMENT.bat",
            "PREPARE_VHF_ALPHA221_PACKAGE.bat",
            "BUILD_VHF_ALPHA222.bat",
            "CHECK_VHF_ALPHA222_ENVIRONMENT.bat",
            "PREPARE_VHF_ALPHA222_PACKAGE.bat",
            "BUILD_VHF_ALPHA230.bat",
            "CHECK_VHF_ALPHA230_SIGNING_READINESS.bat",
            "PREPARE_VHF_ALPHA230_PACKAGE.bat",
            "CREATE_VHF_ALPHA230_SUBMISSION_CAB.bat",
            "VERIFY_VHF_ALPHA230_MICROSOFT_RETURN.bat",
        )
    )
    sources += "\n" + _text(VHF / "tools" / "check_vs2026_wdk.py").lower()
    forbidden = (
        "pnputil",
        "devcon",
        "testsigning",
        "nointegritychecks",
        "sc create",
        "runas",
        "secure boot off",
    )
    assert not any(command in sources for command in forbidden)
    assert "msbuild" in sources
    assert "vhf.h" in sources
    assert "vhfkm.lib" in sources
    assert "dependencia faltante" in sources
    assert "error de compilacion" in sources


def test_no_compiled_or_certificate_payload_is_shipped() -> None:
    forbidden_suffixes = {
        ".sys",
        ".cat",
        ".cab",
        ".pdb",
        ".cer",
        ".pfx",
        ".p12",
        ".hlkx",
    }
    payloads = [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in forbidden_suffixes
    ]
    assert payloads == []


def test_project_metadata_preserves_the_stable_and_alpha1_provenance() -> None:
    metadata = json.loads((ROOT / "VIRTUAL_DUALSENSE_LAB_PROJECT.json").read_text("utf-8"))
    assert metadata["stable_base"]["version"] == "2.9.8.9"
    assert metadata["stable_base"]["original_files_modified"] == 0
    assert metadata["version"] == "3.0.0-alpha.2.3.0"
    assert metadata["alpha212_base_sha256"] == (
        "90c2182889eff299d2e4977e5114bf1075a589a8c3b4d8ba7faefaf003244655"
    )
    assert metadata["alpha213_base_sha256"] == (
        "a11da6c392c549c614371227ce071cd3e196dea78f054b13f35a4dbb8ff9f7b9"
    )
    assert metadata["alpha214_base_sha256"] == (
        "a54dc618d60d6b603e4c5c39649a91c8e9960816daf1c12b1d72e81bd1b46f49"
    )
    assert metadata["alpha215_base_sha256"] == (
        "57eee739ab9069ccb950f5895116f41c4f75efc887cf7d5821efb2558bb1b292"
    )
    assert metadata["alpha214_windows_evidence"]["client_status_exit_code"] == 3
    assert metadata["alpha214_windows_evidence"]["client_reported_win32_error"] == 0
    assert metadata["alpha1_base_sha256"] == (
        "5592243217e3659314bf06905d013096d8c77d0fb4b4b8e16756fcd6b15b0378"
    )
