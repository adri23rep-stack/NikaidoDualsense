"""Backend HID robusto para pydualsense y builds de PyInstaller.

``pydualsense`` importa un módulo llamado ``hidapi`` que usa CFFI y busca una
DLL externa. En instalaciones de desarrollo esa DLL puede estar disponible en
PATH, pero en una distribución PyInstaller no siempre queda incluida. Este
módulo intenta usar el backend original y, si no puede cargarse, instala un
adaptador compatible sobre ``hid`` (cython-hidapi), cuya extensión nativa sí es
empaquetable por PyInstaller.
"""

from __future__ import annotations

import importlib
import logging
import sys
import types
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

_BACKEND_NAME = "uninitialized"
_BACKEND_ERROR = ""


@dataclass(frozen=True)
class HIDBackendStatus:
    name: str
    available: bool
    fallback: bool
    error: str = ""


class _CompatDeviceInfo:
    """Vista por atributos de un diccionario devuelto por ``hid.enumerate``."""

    __slots__ = (
        "path",
        "vendor_id",
        "product_id",
        "serial_number",
        "release_number",
        "manufacturer_string",
        "product_string",
        "usage_page",
        "usage",
        "interface_number",
        "bus_type",
    )

    def __init__(self, raw: dict[str, Any]) -> None:
        self.path = raw.get("path")
        self.vendor_id = int(raw.get("vendor_id") or 0)
        self.product_id = int(raw.get("product_id") or 0)
        self.serial_number = raw.get("serial_number")
        self.release_number = int(raw.get("release_number") or 0)
        self.manufacturer_string = raw.get("manufacturer_string")
        self.product_string = raw.get("product_string")
        self.usage_page = raw.get("usage_page")
        self.usage = raw.get("usage")
        self.interface_number = raw.get("interface_number")
        self.bus_type = raw.get("bus_type")


class _CompatDevice:
    """API mínima de ``hidapi.Device`` implementada con ``hid.device``."""

    def __init__(
        self,
        info: Optional[_CompatDeviceInfo] = None,
        path: Any = None,
        vendor_id: Optional[int] = None,
        product_id: Optional[int] = None,
        serial_number: Optional[str] = None,
        blocking: bool = True,
        *,
        _hid_module: Any,
    ) -> None:
        self._hid_module = _hid_module
        self._device = _hid_module.device()
        self.path = None
        self._closed = False

        if info is not None:
            path = info.path
            self.path = path
        if path is not None:
            if isinstance(path, str):
                path = path.encode("utf-8", errors="surrogateescape")
            self.path = path
            self._device.open_path(path)
        elif vendor_id is not None and product_id is not None:
            self._device.open(int(vendor_id), int(product_id), serial_number)
            try:
                matches = _hid_module.enumerate(int(vendor_id), int(product_id))
                if matches:
                    self.path = matches[0].get("path")
            except Exception:
                self.path = None
        else:
            raise ValueError("Debes indicar info, path o vendor_id/product_id")

        # cython-hidapi usa modo bloqueante de forma predeterminada. Solo se
        # cambia cuando el consumidor lo solicita explícitamente.
        if not blocking:
            self._device.set_nonblocking(1)

    def read(self, length: int, timeout_ms: int = 0, blocking: bool = True):
        if self._closed:
            raise OSError("El dispositivo HID ya está cerrado")
        # En cython-hidapi timeout 0 usa hid_read bloqueante. Esto coincide con
        # el comportamiento que espera pydualsense al llamar read(length).
        if not blocking and not timeout_ms:
            self._device.set_nonblocking(1)
        try:
            return self._device.read(int(length), int(timeout_ms or 0))
        finally:
            if not blocking and not timeout_ms:
                self._device.set_nonblocking(0)

    def write(self, data: Any):
        if self._closed:
            raise OSError("El dispositivo HID ya está cerrado")
        return self._device.write(bytes(data))

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._device.close()

    def get_manufacturer_string(self):
        return self._device.get_manufacturer_string()

    def get_product_string(self):
        return self._device.get_product_string()

    def get_serial_number_string(self):
        return self._device.get_serial_number_string()

    def get_indexed_string(self, index: int):
        return self._device.get_indexed_string(index)

    def send_feature_report(self, data: Any, report_id: int = 0):
        payload = bytes(data)
        if report_id and (not payload or payload[0] != report_id):
            payload = bytes([report_id & 0xFF]) + payload
        return self._device.send_feature_report(payload)

    def get_feature_report(self, report_id: int, length: int):
        return self._device.get_feature_report(int(report_id), int(length))

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()

    def __del__(self) -> None:  # pragma: no cover - depende del GC
        try:
            self.close()
        except Exception:
            pass


def _install_cython_compat(hid_module: Any) -> types.ModuleType:
    module = types.ModuleType("hidapi")
    module.__doc__ = "Compatibilidad hidapi para pydualsense sobre cython-hidapi."
    module.__nikaido_compat__ = True
    module.__version__ = getattr(hid_module, "__version__", "unknown")

    def enumerate_devices(vendor_id: int = 0, product_id: int = 0):
        rows = hid_module.enumerate(int(vendor_id), int(product_id)) or []
        return [_CompatDeviceInfo(dict(row)) for row in rows]

    class Device(_CompatDevice):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, _hid_module=hid_module, **kwargs)

    module.DeviceInfo = _CompatDeviceInfo
    module.Device = Device
    module.enumerate = enumerate_devices
    sys.modules["hidapi"] = module
    return module


def ensure_hidapi_backend() -> HIDBackendStatus:
    """Garantiza que ``import hidapi`` funcione antes de cargar pydualsense."""
    global _BACKEND_NAME, _BACKEND_ERROR

    existing = sys.modules.get("hidapi")
    if existing is not None:
        fallback = bool(getattr(existing, "__nikaido_compat__", False))
        _BACKEND_NAME = "cython-hidapi-compat" if fallback else "hidapi-cffi"
        return HIDBackendStatus(_BACKEND_NAME, True, fallback, _BACKEND_ERROR)

    original_error = ""
    try:
        importlib.import_module("hidapi")
        _BACKEND_NAME = "hidapi-cffi"
        _BACKEND_ERROR = ""
        return HIDBackendStatus(_BACKEND_NAME, True, False, "")
    except Exception as exc:
        original_error = f"{type(exc).__name__}: {exc}"
        sys.modules.pop("hidapi", None)

    try:
        hid_module = importlib.import_module("hid")
        _install_cython_compat(hid_module)
        _BACKEND_NAME = "cython-hidapi-compat"
        _BACKEND_ERROR = original_error
        logger.info(
            "Backend hidapi original no disponible; usando adaptador cython-hidapi (%s)",
            original_error,
        )
        return HIDBackendStatus(_BACKEND_NAME, True, True, original_error)
    except Exception as exc:
        compat_error = f"{type(exc).__name__}: {exc}"
        _BACKEND_NAME = "unavailable"
        _BACKEND_ERROR = (
            f"hidapi original: {original_error or 'no disponible'}; "
            f"adaptador hid: {compat_error}"
        )
        logger.error("No se pudo cargar ningún backend HID: %s", _BACKEND_ERROR)
        return HIDBackendStatus(_BACKEND_NAME, False, False, _BACKEND_ERROR)


def get_hid_backend_status() -> HIDBackendStatus:
    if _BACKEND_NAME == "uninitialized":
        return ensure_hidapi_backend()
    return HIDBackendStatus(
        _BACKEND_NAME,
        _BACKEND_NAME != "unavailable",
        _BACKEND_NAME == "cython-hidapi-compat",
        _BACKEND_ERROR,
    )
