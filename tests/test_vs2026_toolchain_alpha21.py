"""Regresiones portables de la compatibilidad VS2026/WDK de Alpha 2.3.0."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from native.vhf.tools.check_vs2026_wdk import (
    _env_get,
    _human_report,
    evaluate_toolchain,
)
from virtual_dualsense_lab import LAB_NAME, LAB_RELEASE, LAB_VERSION


ROOT = Path(__file__).resolve().parents[1]
VHF = ROOT / "native" / "vhf"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fixture")


def _fake_vs2026(root: Path) -> tuple[Path, Path]:
    vs_install = root / "VS2026"
    for toolset in ("v145", "WindowsKernelModeDriver10.0"):
        _touch(
            vs_install
            / "MSBuild"
            / "Microsoft"
            / "VC"
            / "v180"
            / "Platforms"
            / "x64"
            / "PlatformToolsets"
            / toolset
            / "Toolset.props"
        )
    vc_tools = vs_install / "VC" / "Tools" / "MSVC" / "14.51.36231"
    _touch(vc_tools / "bin" / "Hostx64" / "x64" / "cl.exe")
    _touch(vc_tools / "lib" / "spectre" / "x64" / "libcmt.lib")
    return vs_install, vc_tools


def _fake_kit(root: Path, version: str) -> Path:
    kit = root / "Windows Kits" / "10"
    for relative in (
        Path("Include") / version / "km" / "ntddk.h",
        Path("Include") / version / "shared" / "vhf.h",
        Path("Include") / version / "shared" / "guiddef.h",
        Path("Include") / version / "um" / "Windows.h",
        Path("Lib") / version / "km" / "x64" / "VhfKm.lib",
        Path("Lib") / version / "um" / "x64" / "SetupAPI.lib",
        Path("build") / version / "WindowsDriver.KernelMode.Driver.props",
        Path("build") / version / "bin" / "Microsoft.DriverKit.Build.Tasks.18.0.dll",
    ):
        _touch(kit / relative)
    return kit


def test_alpha22_identity_is_separate_from_alpha215() -> None:
    assert LAB_VERSION == "3.0.0-alpha.2.3.0"
    assert LAB_RELEASE == "Alpha 2.3.0"
    assert LAB_NAME == "Microsoft Signing Readiness"
    metadata = json.loads((ROOT / "VIRTUAL_DUALSENSE_LAB_PROJECT.json").read_text("utf-8"))
    assert metadata["version"] == LAB_VERSION
    assert metadata["alpha2_base_sha256"] == (
        "55c48764c483e2db5f880a443c5d3a6d53b028beb9545581c8c58ea70d744b61"
    )
    assert metadata["alpha21_base_sha256"] == (
        "5fb094b3db4066044e56c3da497fb66361451dc8cf97ecbab9fdd54e1871d3da"
    )
    assert metadata["alpha211_base_sha256"] == (
        "66e0fabb377706b39d4d1c0737435df91e926ea4d453095d6e73245a7e44ed9f"
    )
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


def test_complete_vs2026_wdk_fixture_is_accepted(tmp_path: Path) -> None:
    vs_install, vc_tools = _fake_vs2026(tmp_path)
    kit = _fake_kit(tmp_path, "10.0.28000.0")
    report = evaluate_toolchain(
        msbuild_version="18.8.2.0",
        vs_install=vs_install,
        kit_roots=(kit,),
        explicit_vc_tool_roots=(vc_tools,),
    )
    assert report.ready is True
    assert report.exit_code == 0
    assert report.selected_kit_version == "10.0.28000.0"
    assert all(check.ok for check in report.checks)


def test_missing_wdk_msbuild_integration_is_distinguished(tmp_path: Path) -> None:
    vs_install, vc_tools = _fake_vs2026(tmp_path)
    kernel_props = next(
        path
        for path in vs_install.rglob("Toolset.props")
        if path.parent.name == "WindowsKernelModeDriver10.0"
    )
    kernel_props.unlink()
    kit = _fake_kit(tmp_path, "10.0.28000.0")
    report = evaluate_toolchain(
        msbuild_version="18.8.2.0",
        vs_install=vs_install,
        kit_roots=(kit,),
        explicit_vc_tool_roots=(vc_tools,),
    )
    failed = [check.check_id for check in report.checks if not check.ok]
    assert failed == ["wdk_msbuild_integration"]
    assert report.exit_code == 23


def test_vs2022_kit_family_does_not_pass_the_vs2026_gate(tmp_path: Path) -> None:
    vs_install, vc_tools = _fake_vs2026(tmp_path)
    kit = _fake_kit(tmp_path, "10.0.26100.0")
    report = evaluate_toolchain(
        msbuild_version="18.8.2.0",
        vs_install=vs_install,
        kit_roots=(kit,),
        explicit_vc_tool_roots=(vc_tools,),
    )
    assert report.ready is False
    assert report.exit_code == 24
    assert report.selected_kit_version is None
    assert report.available_kit_builds == (26100,)


def test_missing_vhf_header_is_reported_without_hiding_other_components(
    tmp_path: Path,
) -> None:
    vs_install, vc_tools = _fake_vs2026(tmp_path)
    kit = _fake_kit(tmp_path, "10.0.28000.0")
    (kit / "Include" / "10.0.28000.0" / "shared" / "vhf.h").unlink()
    report = evaluate_toolchain(
        msbuild_version="18.8.2.0",
        vs_install=vs_install,
        kit_roots=(kit,),
        explicit_vc_tool_roots=(vc_tools,),
    )

    assert report.ready is False
    assert report.exit_code == 24
    inspection = report.kit_inspections[0]
    assert inspection.missing_components == ("vhf.h",)
    assert inspection.complete is False
    pair = next(check for check in report.checks if check.check_id == "sdk_wdk_pair")
    assert "falta: vhf.h" in pair.summary
    assert "No repitas la reparación de Visual Studio" in pair.guidance

    human = _human_report(report)
    assert "[FALTA] vhf.h" in human
    assert "[OK   ] ntddk.h" in human
    assert "[OK   ] VhfKm.lib" in human


def test_missing_wdk_build_task_is_reported_before_msbuild(tmp_path: Path) -> None:
    vs_install, vc_tools = _fake_vs2026(tmp_path)
    kit = _fake_kit(tmp_path, "10.0.28000.0")
    task = (
        kit
        / "build"
        / "10.0.28000.0"
        / "bin"
        / "Microsoft.DriverKit.Build.Tasks.18.0.dll"
    )
    task.unlink()
    report = evaluate_toolchain(
        msbuild_version="18.8.2.0",
        vs_install=vs_install,
        kit_roots=(kit,),
        explicit_vc_tool_roots=(vc_tools,),
    )

    assert report.ready is False
    assert report.exit_code == 24
    assert report.kit_inspections[0].missing_components == (
        "Microsoft.DriverKit.Build.Tasks.18.0.dll",
    )
    assert "Microsoft.DriverKit.Build.Tasks.18.0.dll" in _human_report(report)


def test_vhf_header_uses_the_real_wdk_shared_layout(tmp_path: Path) -> None:
    vs_install, vc_tools = _fake_vs2026(tmp_path)
    kit = _fake_kit(tmp_path, "10.0.28000.0")
    shared_header = kit / "Include" / "10.0.28000.0" / "shared" / "vhf.h"
    wrong_kernel_header = kit / "Include" / "10.0.28000.0" / "km" / "vhf.h"
    wrong_kernel_header.parent.mkdir(parents=True, exist_ok=True)
    shared_header.replace(wrong_kernel_header)

    report = evaluate_toolchain(
        msbuild_version="18.8.2.0",
        vs_install=vs_install,
        kit_roots=(kit,),
        explicit_vc_tool_roots=(vc_tools,),
    )

    assert report.ready is False
    assert report.exit_code == 24
    assert report.kit_inspections[0].missing_components == ("vhf.h",)


def test_checker_source_never_regresses_to_the_wrong_vhf_directory() -> None:
    source = _text(VHF / "tools" / "check_vs2026_wdk.py")
    assert '("vhf.h", ("Include", "{version}", "shared", "vhf.h"))' in source
    assert '("vhf.h", ("Include", "{version}", "km", "vhf.h"))' not in source


def test_component_report_is_sanitized_and_machine_readable(tmp_path: Path) -> None:
    vs_install, vc_tools = _fake_vs2026(tmp_path / "private-machine")
    kit = _fake_kit(tmp_path / "private-machine", "10.0.28000.0")
    (kit / "Include" / "10.0.28000.0" / "shared" / "vhf.h").unlink()
    report = evaluate_toolchain(
        msbuild_version="18.8.2.0",
        vs_install=vs_install,
        kit_roots=(kit,),
        explicit_vc_tool_roots=(vc_tools,),
    )

    payload = report.to_dict()
    assert payload["schema_version"] == 2
    assert payload["release"] == "3.0.0-alpha.2.3.0"
    assert payload["kit_inspections"][0]["components"][1] == {
        "name": "vhf.h",
        "status": "missing",
    }
    serialized = json.dumps(payload, ensure_ascii=False)
    assert str(tmp_path) not in serialized
    assert "private-machine" not in serialized


def test_environment_lookup_is_case_insensitive() -> None:
    environment = {
        "programfiles(x86)": "synthetic-program-files",
        "WINDOWSSDKDIR": "synthetic-sdk",
        "wdkcontentroot": "synthetic-wdk",
    }
    assert _env_get(environment, "ProgramFiles(x86)") == "synthetic-program-files"
    assert _env_get(environment, "WindowsSdkDir") == "synthetic-sdk"
    assert _env_get(environment, "WDKContentRoot") == "synthetic-wdk"


def test_components_from_different_roots_are_never_combined(tmp_path: Path) -> None:
    vs_install, vc_tools = _fake_vs2026(tmp_path)
    first = _fake_kit(tmp_path / "first", "10.0.28000.0")
    second = _fake_kit(tmp_path / "second", "10.0.28000.0")
    (first / "Include" / "10.0.28000.0" / "shared" / "vhf.h").unlink()
    (second / "Lib" / "10.0.28000.0" / "km" / "x64" / "VhfKm.lib").unlink()
    report = evaluate_toolchain(
        msbuild_version="18.8.2.0",
        vs_install=vs_install,
        kit_roots=(first, second),
        explicit_vc_tool_roots=(vc_tools,),
    )

    assert report.ready is False
    assert report.selected_kit_version is None
    assert report.kit_inspections[0].complete is False


def test_sanitized_toolchain_report_never_contains_fixture_paths(tmp_path: Path) -> None:
    vs_install, vc_tools = _fake_vs2026(tmp_path / "private-user-path")
    kit = _fake_kit(tmp_path / "private-user-path", "10.0.28000.0")
    report = evaluate_toolchain(
        msbuild_version="18.8.2.0",
        vs_install=vs_install,
        kit_roots=(kit,),
        explicit_vc_tool_roots=(vc_tools,),
    )
    serialized = json.dumps(report.to_dict(), ensure_ascii=False)
    assert str(tmp_path) not in serialized
    assert "private-user-path" not in serialized
    assert report.to_dict()["mutations_performed"] is False


def test_projects_target_vs2026_without_replacing_the_kernel_toolset() -> None:
    driver_project = VHF / "driver" / "NikaidoVirtualHid.vcxproj"
    client_project = VHF / "client" / "NikaidoVhfClient.vcxproj"
    ET.parse(driver_project)
    ET.parse(client_project)
    driver = _text(driver_project)
    client = _text(client_project)
    solution = _text(VHF / "NikaidoVirtualHid.sln")

    assert driver.count("WindowsKernelModeDriver10.0") == 2
    assert driver.count("<DriverTargetPlatform>Universal</DriverTargetPlatform>") == 2
    assert "$(LatestTargetPlatformVersion)" in driver
    assert "<MinimumVisualStudioVersion>18.0</MinimumVisualStudioVersion>" in driver
    assert "<TreatWarningAsError>true</TreatWarningAsError>" in driver
    assert driver.count("<EnableInf2cat>false</EnableInf2cat>") == 1
    assert "<RunInf2Cat>" not in driver
    assert driver.count("<SignMode>Off</SignMode>") == 1
    assert "/PDBALTPATH:%_PDB%" in driver
    assert "_KERNEL_MODE" not in driver
    assert "<PreprocessorDefinitions>UNICODE;_UNICODE;%(PreprocessorDefinitions)" in driver
    assert client.count("<PlatformToolset>v145</PlatformToolset>") == 2
    assert "v143" not in client
    assert "$(LatestTargetPlatformVersion)" in client
    assert "# Visual Studio Version 18" in solution


def test_build_runs_preflight_then_builds_driver_and_client_separately() -> None:
    source = _text(ROOT / "BUILD_VHF_ALPHA230.bat")
    lowered = source.lower()
    clear_record = lowered.index("clear-build-record")
    gate = lowered.index("run_vs2026_wdk_check.bat")
    driver = lowered.index("msbuild native\\vhf\\driver")
    client = lowered.index("msbuild native\\vhf\\client")
    record = lowered.index("record-build")
    assert clear_record < gate < driver < client < record
    assert "nikaidovirtualhid.sln" not in lowered
    assert "error de compilacion - driver" in lowered
    assert "error de compilacion - cliente" in lowered
    assert "dependencia faltante" in lowered


def test_older_command_names_are_non_recursive_compatibility_wrappers() -> None:
    for suffix in ("2", "21", "211", "212", "213", "214", "215", "22", "221", "222"):
        build_name = f"BUILD_VHF_ALPHA{suffix}.bat"
        check_name = f"CHECK_VHF_ALPHA{suffix}_ENVIRONMENT.bat"
        build_wrapper = _text(ROOT / build_name).lower()
        check_wrapper = _text(ROOT / check_name).lower()
        assert build_wrapper.count("build_vhf_alpha230.bat") == 1
        assert check_wrapper.count("check_vhf_alpha230_signing_readiness.bat") == 1
        assert build_wrapper.count("call ") == 1
        assert check_wrapper.count("call ") == 1
        assert f"call {build_name.lower()}" not in build_wrapper
        assert f"call {check_name.lower()}" not in check_wrapper
    for suffix in ("22", "221", "222"):
        prepare_name = f"PREPARE_VHF_ALPHA{suffix}_PACKAGE.bat"
        prepare_wrapper = _text(ROOT / prepare_name).lower()
        assert prepare_wrapper.count("call prepare_vhf_alpha230_package.bat") == 1
        assert prepare_wrapper.count("call ") == 1
        assert f"call {prepare_name.lower()}" not in prepare_wrapper


def test_toolchain_scripts_never_install_or_weaken_windows() -> None:
    paths = (
        ROOT / "BUILD_VHF_ALPHA230.bat",
        ROOT / "CHECK_VHF_ALPHA230_SIGNING_READINESS.bat",
        ROOT / "PREPARE_VHF_ALPHA230_PACKAGE.bat",
        VHF / "tools" / "RUN_VS2026_WDK_CHECK.bat",
        VHF / "tools" / "RUN_VHF_PACKAGE_TOOL.bat",
        VHF / "tools" / "check_vs2026_wdk.py",
        VHF / "tools" / "package_driver.py",
    )
    sources = "\n".join(_text(path).lower() for path in paths)
    forbidden = (
        "pnputil",
        "devcon",
        "bcdedit",
        "testsigning",
        "nointegritychecks",
        "sc create",
        "runas",
        "winget install",
        "choco install",
    )
    assert not any(command in sources for command in forbidden)
    assert "msbuild" in sources
    assert "ntddk.h" in sources
    assert "vhf.h" in sources
    assert "vhfkm.lib" in sources
    assert "microsoft.driverkit.build.tasks.18.0.dll" in sources
    assert "windowskernelmodedriver10.0" in sources


def test_distribution_still_contains_no_native_payload() -> None:
    forbidden_suffixes = {".sys", ".cat", ".cer", ".pfx", ".p12", ".hlkx"}
    payloads = [
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in forbidden_suffixes
    ]
    assert payloads == []
