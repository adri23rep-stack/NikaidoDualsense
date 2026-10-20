"""Integración conservadora con HidHide.

Nikaido nunca modifica filtros del kernel ni elimina configuraciones ajenas.
Usa exclusivamente el cliente/CLI oficial cuando está instalado, agrega su
propio ejecutable a la lista permitida y exige un ID exacto para ocultar o
mostrar dispositivos.
"""

from __future__ import annotations

import json
import logging
import ntpath
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

SONY_VENDOR_MARKERS = ("VID_054C", "VID&0002054C")
DUALSENSE_PRODUCT_MARKERS = ("PID_0CE6", "PID_0DF2", "PID&00020CE6", "PID&00020DF2")


class HidHideManager:
    CACHE_SECONDS = 3.0

    def __init__(self, *, command_runner: Optional[Callable[..., Any]] = None) -> None:
        self._runner = command_runner or subprocess.run
        self._lock = threading.RLock()
        self._last_scan = 0.0
        self._snapshot: Dict[str, Any] = {}
        self._last_error = ""

    @staticmethod
    def is_supported() -> bool:
        return os.name == "nt"

    @staticmethod
    def _registry_info() -> Tuple[str, str]:
        """Detecta la instalación oficial en las vistas reales de Windows.

        HidHide documenta sus claves bajo HKCR. Para evitar que una clave de
        usuario en HKCU suplante una instalación oficial, leemos únicamente la
        parte de máquina que alimenta HKCR: HKLM/Software/Classes, en sus vistas
        de 64 y 32 bits. También aceptamos el servicio del driver como señal de
        instalación cuando el cliente/CLI fue movido o reparado.
        """
        if os.name != "nt":
            return "", ""
        try:
            import winreg
        except ImportError:
            return "", ""

        views = [
            getattr(winreg, "KEY_WOW64_64KEY", 0),
            getattr(winreg, "KEY_WOW64_32KEY", 0),
        ]

        def read_value(root: Any, subkey: str, value_name: str) -> str:
            for view in views:
                try:
                    with winreg.OpenKey(
                        root,
                        subkey,
                        0,
                        winreg.KEY_READ | view,
                    ) as key:
                        return str(winreg.QueryValueEx(key, value_name)[0] or "")
                except OSError:
                    continue
            return ""

        version = ""
        install_path = ""
        for root, version_key, path_key in (
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Classes\Installer\Dependencies\NSS.Drivers.HidHide.x64",
                r"SOFTWARE\Classes\SOFTWARE\Nefarius Software Solutions e.U.\Nefarius Software Solutions e.U. HidHide",
            ),
            # Compatibilidad con instaladores antiguos que escribieron la ruta
            # directamente bajo HKLM en lugar de la vista Classes/HKCR.
            (
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Classes\Installer\Dependencies\NSS.Drivers.HidHide.x64",
                r"SOFTWARE\Nefarius Software Solutions e.U.\Nefarius Software Solutions e.U. HidHide",
            ),
        ):
            version = version or read_value(root, version_key, "Version")
            install_path = install_path or read_value(root, path_key, "Path")

        # Fallback del driver: algunas reparaciones conservan el servicio pero
        # pierden las claves del MSI/cliente. No inventamos una ruta; únicamente
        # señalamos que HidHide está instalado para no mostrar un falso negativo.
        if not version:
            service_image = read_value(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Services\HidHide",
                "ImagePath",
            )
            if service_image:
                version = "driver instalado"
        return version.strip(), install_path.strip().strip('"')

    @staticmethod
    def _known_roots(registry_path: str = "") -> List[Path]:
        program_roots: List[Path] = []
        for env_name in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
            base = os.environ.get(env_name)
            if base:
                program_roots.append(Path(base))

        roots: List[Path] = []
        if registry_path:
            candidate = ntpath.normcase(ntpath.abspath(str(registry_path)))
            for base in program_roots:
                trusted = ntpath.normcase(ntpath.abspath(str(base)))
                try:
                    if ntpath.commonpath([candidate, trusted]) == trusted:
                        roots.append(Path(registry_path))
                        break
                except ValueError:
                    continue
        for base in program_roots:
            # Las versiones/instaladores de HidHide han usado ambos nombres de
            # fabricante. Buscar solo la variante con "e.U" producía falsos
            # negativos en instalaciones válidas bajo Program Files.
            for vendor in (
                "Nefarius Software Solutions e.U",
                "Nefarius Software Solutions",
            ):
                roots.extend(
                    [
                        base / vendor / "HidHide",
                        base / vendor / "HidHideCLI",
                    ]
                )
        unique = []
        seen = set()
        for root in roots:
            key = ntpath.normcase(ntpath.normpath(str(root)))
            if key not in seen:
                unique.append(root)
                seen.add(key)
        return unique

    @classmethod
    def _find_tools(cls, registry_path: str = "") -> Tuple[str, str]:
        cli_names = ("HidHideCLI.exe",)
        client_names = ("HidHideClient.exe", "HidHideConfigClient.exe")
        cli = ""
        client = ""
        roots = cls._known_roots(registry_path)
        for root in roots:
            candidates = [
                root,
                root / "x64",
                root / "x86",
                root / "HidHideCLI",
                root / "HidHide" / "x64",
            ]
            # Búsqueda limitada a dos niveles dentro de raíces confiables de
            # Program Files. Cubre cambios de empaquetado sin escanear carpetas
            # del usuario ni aceptar ejecutables con el mismo nombre en Downloads.
            try:
                for child in root.iterdir() if root.is_dir() else ():
                    if child.is_dir():
                        candidates.append(child)
                        try:
                            candidates.extend(
                                grandchild
                                for grandchild in child.iterdir()
                                if grandchild.is_dir()
                            )
                        except OSError:
                            pass
            except OSError:
                pass
            seen_folders = set()
            for folder in candidates:
                folder_key = ntpath.normcase(ntpath.normpath(str(folder)))
                if folder_key in seen_folders:
                    continue
                seen_folders.add(folder_key)
                if not cli:
                    for name in cli_names:
                        candidate = folder / name
                        if candidate.is_file():
                            cli = str(candidate)
                            break
                if not client:
                    for name in client_names:
                        candidate = folder / name
                        if candidate.is_file():
                            client = str(candidate)
                            break
        return cli, client

    @classmethod
    def _tool_is_trusted(
        cls,
        value: str,
        *,
        registry_path: str = "",
        allowed_names: Iterable[str],
    ) -> bool:
        text = str(value or "").strip().strip('"')
        if not text or ntpath.basename(text).lower() not in {
            str(name).lower() for name in allowed_names
        }:
            return False
        normalized = ntpath.normcase(ntpath.abspath(text))
        for root in cls._known_roots(registry_path):
            root_text = ntpath.normcase(ntpath.abspath(str(root)))
            try:
                if ntpath.commonpath([normalized, root_text]) == root_text:
                    return True
            except ValueError:
                continue
        return False

    def _run_cli(self, cli: str, *arguments: str, timeout: float = 8.0) -> Tuple[int, str, str]:
        if not cli:
            return 127, "", "HidHideCLI no encontrado"
        try:
            result = self._runner(
                [cli, *arguments],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return int(getattr(result, "returncode", 1)), str(getattr(result, "stdout", "") or ""), str(getattr(result, "stderr", "") or "")
        except Exception as exc:
            return 1, "", f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _lines(text: str) -> List[str]:
        return [line.strip() for line in str(text or "").splitlines() if line.strip()]

    @classmethod
    def _parse_command_list(cls, text: str, command: str) -> List[str]:
        """Extrae valores de la salida scriptable del CLI oficial.

        HidHideCLI no devuelve rutas desnudas: ``--app-list`` imprime líneas
        ``--app-reg \"ruta\"`` y ``--dev-list`` imprime ``--dev-hide \"id\"``.
        Se aceptan también líneas desnudas para compatibilidad con versiones
        antiguas y con herramientas de diagnóstico.
        """
        expression = re.compile(
            rf'^\s*--{re.escape(command)}\s+(?:"([^"]+)"|(.+?))\s*$',
            re.IGNORECASE,
        )
        values: List[str] = []
        seen = set()
        for raw_line in str(text or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            match = expression.match(line)
            if match:
                value = str(match.group(1) or match.group(2) or "").strip()
            elif line.startswith("--") or line.startswith("[") or line.startswith("{"):
                continue
            else:
                value = line.strip().strip('"')
            if not value:
                continue
            key = value.casefold()
            if key not in seen:
                values.append(value)
                seen.add(key)
        return values

    @staticmethod
    def _state_from_text(text: str) -> Optional[bool]:
        lowered = str(text or "").strip().lower()
        # Las versiones actuales imprimen --cloak-on/--cloak-off. Se mantienen
        # palabras antiguas, pero sin buscar "on" dentro de cualquier palabra.
        if "--cloak-off" in lowered:
            return False
        if "--cloak-on" in lowered:
            return True
        tokens = set(re.findall(r"[a-záéíóúü]+", lowered))
        negative = {"false", "disabled", "off", "inactivo", "desactivado"}
        positive = {"true", "enabled", "on", "activo", "activado"}
        if tokens & negative:
            return False
        if tokens & positive:
            return True
        return None

    @staticmethod
    def _windows_process_executable() -> str:
        """Obtiene la imagen real del proceso, sin confiar solo en sys.frozen."""
        if os.name != "nt":
            return ""
        try:
            import ctypes

            size = 32768
            buffer = ctypes.create_unicode_buffer(size)
            length = ctypes.windll.kernel32.GetModuleFileNameW(None, buffer, size)
            if 0 < int(length) < size:
                return buffer.value
        except Exception:
            pass
        return ""

    @classmethod
    def current_executable(cls) -> str:
        """Devuelve el proceso real que HidHide debe permitir.

        PyInstaller y Nuitka ejecutan ``Nikaido.exe``. En la edición fuente se
        permite únicamente el Python aislado de ``.venv``; jamás el Python
        global del usuario. Consultar la imagen del proceso también cubre builds
        donde el compilador no define ``sys.frozen``.
        """
        raw = cls._windows_process_executable() or str(sys.executable or "")
        if not raw:
            return ""
        try:
            executable = Path(raw).resolve()
        except OSError:
            executable = Path(os.path.abspath(raw))

        name = executable.name.casefold()
        python_names = {"python.exe", "pythonw.exe", "python", "pythonw"}
        if name not in python_names:
            if getattr(sys, "frozen", False) or name.endswith(".exe"):
                return str(executable)

        lowered_parts = {part.casefold() for part in executable.parts}
        if ".venv" in lowered_parts and name in python_names:
            return str(executable)

        # Desde 2.9.6.4 el runtime fuente vive en una ruta corta para que
        # PySide6 no choque con MAX_PATH. Solo se permite el Python exacto de
        # ese runtime administrado, nunca un Python global cualquiera.
        if name in python_names:
            explicit = str(os.environ.get("NIKAIDO_VENV_DIR", "") or "").strip()
            homes = []
            if explicit:
                homes.append(Path(explicit))
            runtime_home = str(os.environ.get("NIKAIDO_RUNTIME_HOME", "") or "").strip()
            if runtime_home:
                homes.append(Path(runtime_home) / "rt")
            local_app_data = str(os.environ.get("LOCALAPPDATA", "") or "").strip()
            if local_app_data:
                homes.append(Path(local_app_data) / "NKB" / "rt")
            for runtime_dir in homes:
                expected = runtime_dir / "Scripts" / "python.exe"
                try:
                    if executable.resolve() == expected.resolve():
                        return str(executable)
                except OSError:
                    if os.path.normcase(os.path.abspath(str(executable))) == os.path.normcase(
                        os.path.abspath(str(expected))
                    ):
                        return str(executable)
        return ""

    @staticmethod
    def _json_array(text: str) -> Any:
        source = str(text or "").lstrip("\ufeff").strip()
        start = source.find("[")
        end = source.rfind("]")
        if start < 0 or end < start:
            return None
        try:
            return json.loads(source[start : end + 1])
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    @classmethod
    def _parse_gaming_records(cls, text: str) -> List[Dict[str, Any]]:
        """Convierte el JSON de ``--dev-gaming`` en contenedores utilizables."""
        payload = cls._json_array(text)
        records: List[Dict[str, Any]] = []
        if isinstance(payload, list):
            for container in payload:
                if not isinstance(container, dict):
                    continue
                friendly_name = str(container.get("friendlyName") or "").strip()
                devices = container.get("devices")
                if isinstance(devices, dict):
                    devices = [devices]
                if not isinstance(devices, list):
                    devices = []

                preferred_paths: List[str] = []
                all_paths: List[str] = []
                all_seen = set()
                preferred_seen = set()
                searchable = [friendly_name]
                for device in devices:
                    if not isinstance(device, dict):
                        continue
                    for key in (
                        "vendor",
                        "product",
                        "description",
                        "serialNumber",
                        "usage",
                    ):
                        searchable.append(str(device.get(key) or ""))
                    ordered = (
                        str(device.get("baseContainerDeviceInstancePath") or "").strip(),
                        str(device.get("deviceInstancePath") or "").strip(),
                        str(device.get("xusbDeviceInstancePath") or "").strip(),
                    )
                    for candidate in ordered:
                        if not candidate:
                            continue
                        searchable.append(candidate)
                        key = candidate.casefold()
                        if key not in all_seen:
                            all_paths.append(candidate)
                            all_seen.add(key)
                        if key not in preferred_seen:
                            preferred_paths.append(candidate)
                            preferred_seen.add(key)
                if all_paths:
                    records.append(
                        {
                            "friendly_name": friendly_name,
                            "paths": all_paths,
                            "preferred_paths": preferred_paths,
                            "search_text": "\n".join(searchable),
                        }
                    )

        if records:
            return records

        # Fallback para builds antiguas o runners de prueba que devolvían IDs
        # directamente en lugar del JSON documentado por HidHideCLI.
        for value in cls._parse_command_list(text, "dev-hide"):
            records.append(
                {
                    "friendly_name": "",
                    "paths": [value],
                    "preferred_paths": [value],
                    "search_text": value,
                }
            )
        return records

    @staticmethod
    def _is_dualsense_record(record: Dict[str, Any]) -> bool:
        haystack = str(record.get("search_text") or "").upper()
        sony = any(marker in haystack for marker in SONY_VENDOR_MARKERS) or "SONY" in haystack
        product = any(marker in haystack for marker in DUALSENSE_PRODUCT_MARKERS) or "DUALSENSE" in haystack
        return bool(sony and product)

    @classmethod
    def _select_dualsense_devices(
        cls,
        records: Iterable[Dict[str, Any]],
        hidden: Iterable[str],
    ) -> Tuple[List[str], List[str]]:
        hidden_map = {
            str(item).strip().casefold(): str(item).strip()
            for item in hidden
            if str(item).strip()
        }
        devices: List[str] = []
        hidden_devices: List[str] = []
        seen = set()
        for record in records:
            if not cls._is_dualsense_record(record):
                continue
            paths = [str(item).strip() for item in record.get("paths", []) if str(item).strip()]
            preferred = [
                str(item).strip()
                for item in record.get("preferred_paths", [])
                if str(item).strip()
            ]
            hidden_match = next((hidden_map[item.casefold()] for item in paths if item.casefold() in hidden_map), "")
            selected = hidden_match or (preferred[0] if preferred else (paths[0] if paths else ""))
            if not selected:
                continue
            key = selected.casefold()
            if key in seen:
                continue
            seen.add(key)
            devices.append(selected)
            if hidden_match:
                hidden_devices.append(selected)
        return devices, hidden_devices

    @classmethod
    def _stale_nikaido_applications(cls, applications: Iterable[str], target: str) -> List[str]:
        """Encuentra solo entradas viejas de Nikaido en la misma carpeta.

        No usa ``--app-clean`` porque ese comando también borraría entradas
        ajenas. La limpieza se limita al antiguo python.exe/Nikaido.exe ubicado
        junto al ejecutable actual.
        """
        target_text = str(target or "").strip()
        if not target_text:
            return []
        normalized_target = cls._normalize_app_path(target_text)
        target_parent = ntpath.dirname(normalized_target)
        aliases = {"python.exe", "pythonw.exe", "nikaido.exe", "nikaido dualsense.exe"}
        stale: List[str] = []
        for value in applications:
            application = str(value or "").strip()
            normalized = cls._normalize_app_path(application)
            if not normalized or normalized == normalized_target:
                continue
            if ntpath.dirname(normalized) != target_parent:
                continue
            if ntpath.basename(normalized).casefold() in aliases:
                stale.append(application)
        return stale

    @staticmethod
    def _device_path_to_dos_path(value: str) -> str:
        """Convierte una ruta NT de dispositivo a una ruta con letra de unidad."""
        text = str(value or "").strip()
        if os.name != "nt" or not text.casefold().startswith("\\\\device\\"):
            return text
        try:
            import ctypes

            buffer = ctypes.create_unicode_buffer(32768)
            for code in range(ord("A"), ord("Z") + 1):
                drive = f"{chr(code)}:"
                if not ctypes.windll.kernel32.QueryDosDeviceW(
                    drive, buffer, len(buffer)
                ):
                    continue
                target = buffer.value
                if text.casefold().startswith(target.casefold() + "\\"):
                    return drive + text[len(target):]
        except Exception:
            pass
        return text

    @classmethod
    def _normalize_app_path(cls, value: str) -> str:
        text = str(value or "").strip().strip('"')
        if not text:
            return ""
        if text.startswith("\\\\?\\"):
            text = text[4:]
        text = cls._device_path_to_dos_path(text)
        # HidHide devuelve rutas de Windows. ntpath mantiene una comparación
        # correcta incluso durante pruebas o herramientas ejecutadas fuera de Windows.
        return ntpath.normcase(ntpath.normpath(text))

    def scan(self, *, force: bool = False, emulator_active: bool = False) -> Dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            if not force and self._snapshot and now - self._last_scan < self.CACHE_SECONDS:
                result = dict(self._snapshot)
                result["duplicate_risk"] = bool(
                    emulator_active
                    and result.get("dualsense_devices")
                    and not result.get("ready")
                )
                return result

        supported = self.is_supported()
        version, registry_path = self._registry_info() if supported else ("", "")
        cli, client = self._find_tools(registry_path) if supported else ("", "")
        installed = bool(version or registry_path or cli or client)
        apps: List[str] = []
        hidden: List[str] = []
        gaming_records: List[Dict[str, Any]] = []
        cloak_enabled: Optional[bool] = None
        command_errors: List[str] = []

        if cli:
            code, stdout, stderr = self._run_cli(cli, "--app-list")
            if code == 0:
                apps = self._parse_command_list(stdout, "app-reg")
            else:
                command_errors.append(stderr or f"--app-list devolvió {code}")

            code, stdout, stderr = self._run_cli(cli, "--dev-list")
            if code == 0:
                hidden = self._parse_command_list(stdout, "dev-hide")
            else:
                command_errors.append(stderr or f"--dev-list devolvió {code}")

            code, stdout, stderr = self._run_cli(cli, "--dev-gaming")
            if code == 0:
                gaming_records = self._parse_gaming_records(stdout)
            else:
                command_errors.append(stderr or f"--dev-gaming devolvió {code}")

            code, stdout, stderr = self._run_cli(cli, "--cloak-state")
            if code == 0:
                cloak_enabled = self._state_from_text(stdout)
            else:
                command_errors.append(stderr or f"--cloak-state devolvió {code}")

        gaming: List[str] = []
        gaming_seen = set()
        for record in gaming_records:
            for item in record.get("paths", []):
                value = str(item or "").strip()
                key = value.casefold()
                if value and key not in gaming_seen:
                    gaming.append(value)
                    gaming_seen.add(key)

        executable = self.current_executable()
        normalized_apps = {self._normalize_app_path(item) for item in apps if item}
        whitelisted = bool(
            executable and self._normalize_app_path(executable) in normalized_apps
        )
        stale_apps = self._stale_nikaido_applications(apps, executable)
        dualsense, dualsense_hidden = self._select_dualsense_devices(
            gaming_records,
            hidden,
        )
        ready = bool(installed and cloak_enabled is True and whitelisted and dualsense_hidden)
        issues = []
        if supported and not installed:
            issues.append("HidHide no está instalado")
        elif installed:
            if not cli:
                issues.append("No se encontró HidHideCLI")
            if cloak_enabled is False:
                issues.append("El ocultamiento está desactivado")
            if executable and not whitelisted:
                issues.append("Nikaido.exe no está en aplicaciones permitidas")
            if stale_apps:
                issues.append("Hay una entrada antigua de Nikaido en aplicaciones permitidas")
            if dualsense and not dualsense_hidden:
                issues.append("El DualSense físico no está oculto")
        if command_errors:
            issues.append("El CLI respondió con errores; abre el cliente oficial")

        snapshot = {
            "supported": supported,
            "installed": installed,
            "version": version,
            "install_path": registry_path,
            "cli_path": cli,
            "client_path": client,
            "cloak_enabled": cloak_enabled,
            "applications": apps,
            "hidden_devices": hidden,
            "gaming_devices": gaming,
            "gaming_records": gaming_records,
            "dualsense_devices": dualsense,
            "dualsense_hidden": dualsense_hidden,
            "nikaido_executable": executable,
            "nikaido_whitelisted": whitelisted,
            "stale_nikaido_applications": stale_apps,
            "ready": ready,
            "issues": issues,
            "command_errors": command_errors[-4:],
            "duplicate_risk": bool(emulator_active and dualsense and not ready),
            "scanned_at": time.time(),
        }
        with self._lock:
            self._snapshot = dict(snapshot)
            self._last_scan = now
            self._last_error = command_errors[-1] if command_errors else ""
        return snapshot

    def _require_cli(self) -> str:
        snapshot = self.scan(force=True)
        cli = str(snapshot.get("cli_path") or "")
        if not cli:
            raise RuntimeError("HidHideCLI no está disponible")
        return cli

    def whitelist_nikaido(self, executable: str = "") -> bool:
        target = str(executable or self.current_executable()).strip()
        if not target:
            raise RuntimeError(
                "No se pudo identificar el proceso de Nikaido. Ábrelo con "
                "INICIAR_NIKAIDO.bat o usa el ejecutable compilado."
            )
        target_path = Path(target).resolve()
        if not target_path.is_file():
            raise FileNotFoundError(str(target_path))

        snapshot = self.scan(force=True)
        cli = str(snapshot.get("cli_path") or "")
        if not cli:
            raise RuntimeError("HidHideCLI no está disponible")

        applications = [str(item) for item in snapshot.get("applications") or []]
        normalized_target = self._normalize_app_path(str(target_path))
        normalized_apps = {self._normalize_app_path(item) for item in applications}
        if normalized_target not in normalized_apps:
            code, _stdout, stderr = self._run_cli(cli, "--app-reg", str(target_path))
            if code != 0:
                raise RuntimeError(stderr or f"HidHideCLI devolvió {code}")

        # Quita únicamente runtimes viejos ubicados junto al EXE actual. Esto
        # corrige la entrada roja python.exe sin tocar aplicaciones de terceros.
        stale_entries = self._stale_nikaido_applications(applications, str(target_path))
        for stale in stale_entries:
            code, _stdout, stderr = self._run_cli(cli, "--app-unreg", stale)
            if code != 0:
                logger.warning(
                    "No se pudo retirar la entrada antigua de HidHide %s: %s",
                    stale,
                    stderr or code,
                )

        self.scan(force=True)
        return True

    def set_cloak_enabled(self, enabled: bool) -> bool:
        # Antes de cerrar la capa, asegura que el proceso real de Nikaido pueda
        # seguir viendo el control. También repara la entrada vieja python.exe.
        if enabled:
            self.whitelist_nikaido()
        cli = self._require_cli()
        code, _stdout, stderr = self._run_cli(cli, "--cloak-on" if enabled else "--cloak-off")
        if code != 0:
            raise RuntimeError(stderr or f"HidHideCLI devolvió {code}")
        self.scan(force=True)
        return True

    def set_device_hidden(self, instance_id: str, hidden: bool) -> bool:
        value = str(instance_id or "").strip()
        if (
            not value
            or len(value) > 1_024
            or any(ch in value for ch in "\r\n\x00")
            or not re.match(
                r"^(?:HID|USB|BTHENUM|BTHLEDEVICE)\\[A-Za-z0-9_&\\#{}().?+:%-]+$",
                value,
                re.I,
            )
        ):
            raise ValueError("Selecciona un ID de dispositivo HID válido")
        if hidden:
            self.whitelist_nikaido()
        cli = self._require_cli()
        argument = "--dev-hide" if hidden else "--dev-unhide"
        code, _stdout, stderr = self._run_cli(cli, argument, value)
        if code != 0:
            raise RuntimeError(stderr or f"HidHideCLI devolvió {code}")
        self.scan(force=True)
        return True

    def open_client(self) -> bool:
        snapshot = self.scan(force=True)
        client = str(snapshot.get("client_path") or "")
        registry_path = str(snapshot.get("install_path") or "")
        if not client or not self._tool_is_trusted(
            client,
            registry_path=registry_path,
            allowed_names=("HidHideClient.exe", "HidHideConfigClient.exe"),
        ):
            return False
        subprocess.Popen([client], close_fds=True)
        return True

    def launch_installer(self) -> bool:
        """Abre la publicación oficial sin ejecutar gestores hallados en rutas de usuario."""
        if os.name != "nt":
            return False
        return bool(webbrowser.open("https://github.com/nefarius/HidHide/releases/latest", new=2))

    def get_diagnostics_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            snapshot = dict(self._snapshot)
            snapshot["last_error"] = self._last_error
            return snapshot
