"""Reparación conservadora de la conexión Bluetooth del DualSense.

La versión anterior borraba claves de emparejamiento de todo el adaptador. Eso
podía desconectar audífonos, teclados y otros dispositivos. Este módulo solo
reinicia el servicio y refresca dispositivos que coinciden con DualSense.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from .security_utils import redact_private_text

logger = logging.getLogger(__name__)

_FIND_DUALSENSE = (
    "Get-PnpDevice -Class Bluetooth | "
    "Where-Object { $_.FriendlyName -like '*DualSense*' -or "
    "$_.FriendlyName -like '*Wireless Controller*' } | "
    "Select-Object -ExpandProperty InstanceId"
)
_DISABLE_DUALSENSE = (
    "Get-PnpDevice -Class Bluetooth | "
    "Where-Object { $_.FriendlyName -like '*DualSense*' -or "
    "$_.FriendlyName -like '*Wireless Controller*' } | "
    "Disable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue"
)
_ENABLE_DUALSENSE = (
    "Get-PnpDevice -Class Bluetooth | "
    "Where-Object { $_.FriendlyName -like '*DualSense*' -or "
    "$_.FriendlyName -like '*Wireless Controller*' } | "
    "Enable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue"
)
_STOP_SERVICE = (
    "Stop-Service -Name 'bthserv' -Force -ErrorAction SilentlyContinue; "
    "Start-Sleep -Seconds 2"
)
_START_SERVICE = "Start-Service -Name 'bthserv' -ErrorAction SilentlyContinue"
_ALLOWED_SCRIPTS = {
    _FIND_DUALSENSE,
    _DISABLE_DUALSENSE,
    _ENABLE_DUALSENSE,
    _STOP_SERVICE,
    _START_SERVICE,
}


class BluetoothManager:
    """Gestiona una reparación Bluetooth de alcance limitado."""

    def __init__(self):
        self._cleanup_lock = threading.Lock()
        self._last_cleanup_time: Optional[float] = None
        self._status_callback: Optional[Callable[[str], None]] = None

    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        self._status_callback = callback

    def _report_status(self, message: str) -> None:
        safe = redact_private_text(message)
        logger.info(safe)
        if self._status_callback:
            try:
                self._status_callback(safe)
            except Exception:
                pass

    @staticmethod
    def _powershell_path() -> str:
        """Usa únicamente el PowerShell firmado que forma parte de Windows."""
        if os.name != "nt":
            return ""
        windows = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
        if not windows:
            return ""
        candidate = (
            Path(windows)
            / "System32"
            / "WindowsPowerShell"
            / "v1.0"
            / "powershell.exe"
        )
        return str(candidate) if candidate.is_file() else ""

    def _run_powershell(self, command: str, description: str) -> tuple[bool, str]:
        """Ejecuta solo scripts internos conocidos, sin PATH ni perfil de usuario."""
        if command not in _ALLOWED_SCRIPTS:
            self._report_status(f"✗ {description}: operación no permitida")
            return False, "Operación PowerShell no permitida"
        executable = self._powershell_path()
        if not executable:
            self._report_status(f"✗ {description}: PowerShell del sistema no disponible")
            return False, "PowerShell del sistema no disponible"
        try:
            result = subprocess.run(
                [
                    executable,
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    command,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                self._report_status(f"✓ {description}")
                return True, str(result.stdout or "").strip()
            error_msg = str(result.stderr or "Error desconocido").strip()
            self._report_status(f"✗ {description}: {error_msg}")
            return False, redact_private_text(error_msg)
        except subprocess.TimeoutExpired:
            self._report_status(f"✗ {description}: tiempo agotado")
            return False, "Tiempo agotado"
        except Exception as exc:
            error = redact_private_text(f"{type(exc).__name__}: {exc}")
            self._report_status(f"✗ {description}: {error}")
            return False, error

    def restart_bluetooth_service(self) -> bool:
        self._report_status("Reiniciando servicio Bluetooth...")
        stopped, _ = self._run_powershell(_STOP_SERVICE, "Servicio Bluetooth detenido")
        time.sleep(0.5)
        started, _ = self._run_powershell(_START_SERVICE, "Servicio Bluetooth iniciado")
        return bool(stopped and started)

    def remove_dualsense_pairing(self) -> bool:
        """Refresca el DualSense sin borrar su emparejamiento ni el de otros equipos."""
        self._report_status("Buscando DualSense Bluetooth...")
        success, output = self._run_powershell(
            _FIND_DUALSENSE,
            "Búsqueda de DualSense emparejado",
        )
        if not success:
            return False
        if not output.strip():
            self._report_status("No se encontró un DualSense Bluetooth para refrescar")
            return True
        disabled, _ = self._run_powershell(
            _DISABLE_DUALSENSE,
            "DualSense deshabilitado temporalmente",
        )
        if not disabled:
            return False
        time.sleep(0.6)
        enabled, _ = self._run_powershell(
            _ENABLE_DUALSENSE,
            "DualSense habilitado",
        )
        return enabled

    def clear_bluetooth_cache(self) -> bool:
        """Compatibilidad: ya no borra claves globales del adaptador."""
        self._report_status(
            "Limpieza destructiva omitida: Nikaido conserva audífonos, teclados y otros emparejamientos"
        )
        return True

    def full_bluetooth_reset(self, callback: Optional[Callable[[str], None]] = None) -> bool:
        # El check anterior usaba un booleano sin protección: dos clics/hilos
        # podían observar False y reiniciar el servicio simultáneamente.
        if not self._cleanup_lock.acquire(blocking=False):
            self._report_status("Reparación ya en progreso...")
            return False
        try:
            if callback:
                self._status_callback = callback

            self._report_status("=== INICIANDO REPARACIÓN BLUETOOTH SEGURA ===")
            device_ok = self.remove_dualsense_pairing()
            time.sleep(0.5)
            self.clear_bluetooth_cache()
            service_ok = self.restart_bluetooth_service()
            self._last_cleanup_time = time.time()
            success = bool(device_ok and service_ok)
            self._report_status(
                "=== REPARACIÓN BLUETOOTH COMPLETADA ==="
                if success
                else "=== REPARACIÓN BLUETOOTH CON ADVERTENCIAS ==="
            )
            return success
        except Exception as exc:
            self._report_status(f"Error en reparación Bluetooth: {exc}")
            return False
        finally:
            self._cleanup_lock.release()

    def is_cleanup_in_progress(self) -> bool:
        return self._cleanup_lock.locked()

    def get_last_cleanup_time(self) -> Optional[float]:
        return self._last_cleanup_time
