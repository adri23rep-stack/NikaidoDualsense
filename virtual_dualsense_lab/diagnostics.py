"""Diagnóstico de solo lectura para la viabilidad de un HID virtual."""

from __future__ import annotations

import ctypes
import os
import platform
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from .version import (
    DIAGNOSTIC_SCHEMA_VERSION,
    LAB_NAME,
    LAB_RELEASE,
    LAB_VERSION,
    PRODUCT_NAME,
    PUBLISHER,
)


class CheckStatus(str, Enum):
    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    check_id: str
    status: CheckStatus
    summary: str
    required_for_native: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.check_id,
            "status": self.status.value,
            "summary": self.summary,
            "required_for_native": self.required_for_native,
        }


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    generated_utc: str
    platform_name: str
    platform_release: str
    architecture: str
    python_version: str
    checks: tuple[DiagnosticCheck, ...]
    native_blockers: tuple[str, ...]
    simulation_ready: bool = True
    native_prototype_allowed: bool = False
    native_source_present: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
            "product": PRODUCT_NAME,
            "lab": LAB_NAME,
            "version": LAB_VERSION,
            "release": LAB_RELEASE,
            "publisher": PUBLISHER,
            "generated_utc": self.generated_utc,
            "environment": {
                "platform": self.platform_name,
                "release": self.platform_release,
                "architecture": self.architecture,
                "python": self.python_version,
            },
            "simulation": {
                "ready": self.simulation_ready,
                "reports_to_os": False,
            },
            "native_hid": {
                "allowed": self.native_prototype_allowed,
                "status": "blocked",
                "blockers": list(self.native_blockers),
                "driver_source_included": self.native_source_present,
                "inf_source_included": self.native_source_present,
                "client_source_included": self.native_source_present,
                "compiled_driver_included": False,
                "driver_included": False,
                "driver_installed": False,
                "driver_signed": False,
            },
            "safety_policy": {
                "automatic_driver_installation": False,
                "automatic_elevation": False,
                "enable_test_signing": False,
                "disable_secure_boot": False,
                "disable_memory_integrity": False,
                "modify_boot_configuration": False,
                "reuse_stable_emulation_backend": False,
                "integrated_into_main_ui": False,
            },
            "checks": [check.to_dict() for check in self.checks],
            "privacy": {
                "contains_username": False,
                "contains_hostname": False,
                "contains_private_paths": False,
                "contains_device_instance_ids": False,
            },
        }


def _registry_dword(subkey: str, value_name: str) -> Optional[int]:
    if os.name != "nt":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey, 0, winreg.KEY_READ) as key:
            value, _kind = winreg.QueryValueEx(key, value_name)
        return int(value)
    except (ImportError, OSError, TypeError, ValueError):
        return None


def _service_exists(service_name: str) -> Optional[bool]:
    if os.name != "nt":
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", service_name):
        raise ValueError("Nombre de servicio inválido")
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            rf"SYSTEM\CurrentControlSet\Services\{service_name}",
            0,
            winreg.KEY_READ,
        ):
            return True
    except FileNotFoundError:
        return False
    except (ImportError, OSError):
        return None


def _windows_build() -> Optional[int]:
    if os.name != "nt" or not hasattr(sys, "getwindowsversion"):
        return None
    try:
        return int(sys.getwindowsversion().build)
    except (AttributeError, TypeError, ValueError):
        return None


def _is_admin() -> Optional[bool]:
    if os.name != "nt":
        return None
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return None


def _test_signing_enabled() -> Optional[bool]:
    """Lee el estado efectivo de Code Integrity sin ejecutar procesos ni cambiar el BCD."""

    if os.name != "nt":
        return None

    class SystemCodeIntegrityInformation(ctypes.Structure):
        _fields_ = [
            ("Length", ctypes.c_ulong),
            ("CodeIntegrityOptions", ctypes.c_ulong),
        ]

    # SystemCodeIntegrityInformation (103) y CODEINTEGRITY_OPTION_TESTSIGN (0x02)
    # están definidos por la API de NtQuerySystemInformation de Windows.
    try:
        information = SystemCodeIntegrityInformation()
        information.Length = ctypes.sizeof(information)
        query = ctypes.windll.ntdll.NtQuerySystemInformation
        query.argtypes = [
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_void_p,
        ]
        query.restype = ctypes.c_long
        status = query(
            103,
            ctypes.byref(information),
            ctypes.sizeof(information),
            None,
        )
    except (AttributeError, OSError, TypeError, ValueError):
        return None
    if status != 0:
        return None
    return bool(information.CodeIntegrityOptions & 0x02)


def _wdk_detected() -> bool:
    """Comprueba ubicaciones genéricas sin publicar ninguna ruta del equipo."""

    candidates = []
    for variable in ("WDKContentRoot", "WindowsSdkDir"):
        value = os.environ.get(variable)
        if value:
            candidates.append(Path(value))
    program_files = os.environ.get("ProgramFiles(x86)")
    if program_files:
        candidates.append(Path(program_files) / "Windows Kits" / "10" / "Include")
    return any(candidate.is_dir() for candidate in candidates)


def _native_source_present() -> bool:
    root = Path(__file__).resolve().parents[1] / "native" / "vhf"
    required = (
        root / "driver" / "driver.c",
        root / "driver" / "NikaidoVirtualHid.inf",
        root / "driver" / "NikaidoVirtualHid.vcxproj",
        root / "client" / "main.cpp",
        root / "client" / "NikaidoVhfClient.vcxproj",
        root / "shared" / "nikaido_vhf_protocol.h",
    )
    return all(path.is_file() for path in required)


def _package_preparation_source_present() -> bool:
    root = Path(__file__).resolve().parents[1]
    required = (
        root / "PREPARE_VHF_ALPHA230_PACKAGE.bat",
        root / "native" / "vhf" / "tools" / "package_driver.py",
        root / "native" / "vhf" / "tools" / "RUN_VHF_PACKAGE_TOOL.bat",
    )
    return all(path.is_file() for path in required)


def _signing_readiness_source_present() -> bool:
    root = Path(__file__).resolve().parents[1]
    required = (
        root / "CREATE_VHF_ALPHA230_SUBMISSION_CAB.bat",
        root / "VERIFY_VHF_ALPHA230_MICROSOFT_RETURN.bat",
        root / "native" / "vhf" / "tools" / "signing_readiness.py",
        root / "native" / "vhf" / "tools" / "RUN_VHF_SIGNING_TOOL.bat",
    )
    return all(path.is_file() for path in required)


def collect_diagnostics() -> DiagnosticReport:
    system = platform.system() or "Unknown"
    release = platform.release() or "Unknown"
    architecture = platform.machine() or "Unknown"
    is_windows = os.name == "nt" and system.lower() == "windows"
    checks: list[DiagnosticCheck] = []
    blockers: list[str] = []

    python_ok = sys.version_info >= (3, 10)
    checks.append(
        DiagnosticCheck(
            "python_version",
            CheckStatus.OK if python_ok else CheckStatus.BLOCKED,
            "Python 3.10 o superior disponible" if python_ok else "Se requiere Python 3.10 o superior",
            required_for_native=False,
        )
    )

    if is_windows:
        checks.append(
            DiagnosticCheck(
                "windows_platform",
                CheckStatus.OK,
                "Windows detectado",
                required_for_native=True,
            )
        )
    else:
        blockers.append("El prototipo nativo solo puede compilarse y validarse en Windows")
        checks.append(
            DiagnosticCheck(
                "windows_platform",
                CheckStatus.BLOCKED,
                "Entorno no Windows; solo el simulador es verificable",
                required_for_native=True,
            )
        )

    normalized_arch = architecture.lower()
    x64 = normalized_arch in {"amd64", "x86_64"}
    if not x64:
        blockers.append("Alpha 2.3.0 no define un paquete nativo para esta arquitectura")
    checks.append(
        DiagnosticCheck(
            "architecture_x64",
            CheckStatus.OK if x64 else CheckStatus.BLOCKED,
            "Arquitectura x64 detectada"
            if x64
            else "Arquitectura nativa fuera del alcance Alpha 2.3.0",
            required_for_native=True,
        )
    )

    build = _windows_build()
    vhf_available = build is not None and build >= 10240
    if is_windows and vhf_available:
        checks.append(
            DiagnosticCheck(
                "windows_vhf_api",
                CheckStatus.OK,
                "La versión de Windows admite VHF/UDE; todavía requiere un driver firmado",
                required_for_native=True,
            )
        )
    else:
        checks.append(
            DiagnosticCheck(
                "windows_vhf_api",
                CheckStatus.BLOCKED if is_windows else CheckStatus.INFO,
                "VHF/UDE no puede verificarse en este entorno",
                required_for_native=True,
            )
        )
        if is_windows:
            blockers.append("No se pudo confirmar una versión de Windows compatible con VHF")

    secure_boot = _registry_dword(
        r"SYSTEM\CurrentControlSet\Control\SecureBoot\State",
        "UEFISecureBootEnabled",
    )
    if secure_boot is None:
        secure_boot_status = CheckStatus.INFO if not is_windows else CheckStatus.UNKNOWN
        secure_boot_summary = "Secure Boot no aplica en este entorno" if not is_windows else "Estado de Secure Boot no disponible en modo de solo lectura"
    elif secure_boot:
        secure_boot_status = CheckStatus.OK
        secure_boot_summary = "Secure Boot está habilitado; el laboratorio no lo modificará"
    else:
        secure_boot_status = CheckStatus.WARNING
        secure_boot_summary = "Secure Boot aparece deshabilitado; el laboratorio no cambiará su estado"
    checks.append(DiagnosticCheck("secure_boot", secure_boot_status, secure_boot_summary))

    memory_integrity = _registry_dword(
        r"SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity",
        "Enabled",
    )
    if memory_integrity is None:
        memory_status = CheckStatus.INFO if not is_windows else CheckStatus.UNKNOWN
        memory_summary = "Integridad de memoria no aplica en este entorno" if not is_windows else "Configuración de Integridad de memoria no disponible"
    elif memory_integrity:
        memory_status = CheckStatus.OK
        memory_summary = "Integridad de memoria está habilitada; cualquier driver futuro deberá ser compatible"
    else:
        memory_status = CheckStatus.WARNING
        memory_summary = "Integridad de memoria aparece deshabilitada; el laboratorio no cambiará su estado"
    checks.append(DiagnosticCheck("memory_integrity", memory_status, memory_summary))

    test_signing = _test_signing_enabled()
    if test_signing is None:
        signing_status = CheckStatus.INFO if not is_windows else CheckStatus.UNKNOWN
        signing_summary = "Test signing no aplica en este entorno" if not is_windows else "No se pudo leer el estado de test signing"
    elif test_signing:
        signing_status = CheckStatus.WARNING
        signing_summary = "Test signing ya está habilitado; el laboratorio no lo usará ni modificará"
    else:
        signing_status = CheckStatus.OK
        signing_summary = "Test signing está deshabilitado y permanecerá sin cambios"
    checks.append(DiagnosticCheck("test_signing", signing_status, signing_summary))

    admin = _is_admin()
    checks.append(
        DiagnosticCheck(
            "process_elevation",
            CheckStatus.INFO,
            "Proceso elevado detectado; no se realizarán cambios" if admin else "El diagnóstico no solicita elevación",
        )
    )

    for service_name, check_id, label in (
        ("ViGEmBus", "existing_vigembus", "ViGEmBus"),
        ("HidHide", "existing_hidhide", "HidHide"),
    ):
        exists = _service_exists(service_name)
        summary = (
            f"{label} detectado; pertenece a la emulación estable y no será modificado"
            if exists
            else f"{label} no detectado o no aplicable; no se instalará"
        )
        checks.append(DiagnosticCheck(check_id, CheckStatus.INFO, summary))

    lab_service = _service_exists("NikaidoVirtualHid")
    checks.append(
        DiagnosticCheck(
            "lab_driver_service",
            CheckStatus.WARNING if lab_service else CheckStatus.OK,
            "Existe un servicio con el nombre reservado del laboratorio; revísalo manualmente"
            if lab_service
            else "No hay driver del laboratorio instalado, como corresponde al paquete fuente Alpha 2.3.0",
            required_for_native=True,
        )
    )
    if lab_service:
        blockers.append("Ya existe un servicio externo con el nombre reservado del laboratorio")

    checks.append(
        DiagnosticCheck(
            "wdk",
            CheckStatus.INFO,
            (
                "Archivos WDK detectados; la integración de MSBuild se valida por separado"
                if _wdk_detected()
                else "WDK no detectado; no es necesario para el simulador"
            ),
            required_for_native=True,
        )
    )

    native_source = _native_source_present()
    checks.append(
        DiagnosticCheck(
            "native_driver_source",
            CheckStatus.OK if native_source else CheckStatus.BLOCKED,
            "Código fuente KMDF/VHF, INF y cliente de prueba presentes"
            if native_source
            else "Falta uno o más componentes del prototipo fuente KMDF/VHF",
            required_for_native=True,
        )
    )
    if not native_source:
        blockers.append("El prototipo fuente KMDF/VHF está incompleto")
    package_source = _package_preparation_source_present()
    checks.append(
        DiagnosticCheck(
            "native_package_preparation_source",
            CheckStatus.OK if package_source else CheckStatus.BLOCKED,
            "Comprobador InfVerif/Inf2Cat y preparador de paquete fuente presentes"
            if package_source
            else "Falta uno o más componentes del preparador de paquete Alpha 2.3.0",
            required_for_native=True,
        )
    )
    if not package_source:
        blockers.append("El preparador de paquete Alpha 2.3.0 está incompleto")
    signing_source = _signing_readiness_source_present()
    checks.append(
        DiagnosticCheck(
            "native_signing_readiness_source",
            CheckStatus.OK if signing_source else CheckStatus.BLOCKED,
            (
                "Preparador CAB y verificador de respuesta firmada presentes"
                if signing_source
                else "Falta uno o más componentes de firma segura Alpha 2.3.0"
            ),
            required_for_native=True,
        )
    )
    if not signing_source:
        blockers.append("La preparación de firma Alpha 2.3.0 está incompleta")
    blockers.extend(
        [
            "El código fuente Alpha 2.3.0 no fue compilado con WDK en este paquete",
            "Alpha 2.3.0 no incluye un paquete de driver firmado por Microsoft",
            "El backend nativo no fue probado con Windows, HLK, Driver Verifier ni HVCI",
        ]
    )
    checks.extend(
        [
            DiagnosticCheck(
                "native_driver_payload",
                CheckStatus.BLOCKED,
                "Se incluye INF fuente, pero no .sys, CAT ni instalador de driver",
                required_for_native=True,
            ),
            DiagnosticCheck(
                "production_signature",
                CheckStatus.BLOCKED,
                "No existe todavía un paquete con firma de producción verificable",
                required_for_native=True,
            ),
            DiagnosticCheck(
                "native_backend_implementation",
                CheckStatus.BLOCKED,
                "El adaptador Python permanece sellado hasta compilar, firmar y validar el driver",
                required_for_native=True,
            ),
        ]
    )

    return DiagnosticReport(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        platform_name=system,
        platform_release=release,
        architecture=architecture,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        checks=tuple(checks),
        native_blockers=tuple(dict.fromkeys(blockers)),
        simulation_ready=python_ok,
        native_prototype_allowed=False,
        native_source_present=native_source,
    )
