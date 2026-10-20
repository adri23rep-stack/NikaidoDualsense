"""Control seguro del micrófono de Windows y del botón MIC del DualSense.

El acceso a Core Audio/COM vive en un hilo dedicado. De esta forma, enumerar
un dispositivo lento o una llamada de Windows bloqueada nunca retrasa la ruta
HID -> remapeo -> ViGEm del controlador.
"""

from __future__ import annotations

import copy
import logging
import math
import os
import queue
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

logger = logging.getLogger(__name__)

# El botón MIC silencia por defecto cualquier micrófono activo del PC. Quien
# prefiera un solo dispositivo puede elegir "selected" en cada perfil.
DEFAULT_TARGET_MODE = "all"
TARGET_MODES = ("selected", "all", "all_except_dualsense")

DEFAULT_AUDIO_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "button_enabled": True,
    # selected: un dispositivo; all: todos; all_except_dualsense: todos menos
    # la entrada de audio integrada del control.
    "target_mode": DEFAULT_TARGET_MODE,
    "device_id": "default",
    "led_sync": True,
    "apply_volume": False,
    "volume": 100,
    # keep: conservar el estado actual; muted/unmuted: forzarlo al aplicar perfil.
    "profile_mute_mode": "keep",
}


@dataclass(frozen=True)
class AudioDeviceInfo:
    id: str
    name: str
    is_default: bool = False
    is_dualsense: bool = False


@dataclass(frozen=True)
class AudioEndpointState:
    device_id: str
    name: str
    muted: bool
    volume: int


def _bounded_int(value: Any, minimum: int, maximum: int, fallback: int) -> int:
    try:
        return max(minimum, min(maximum, int(float(value))))
    except (TypeError, ValueError, OverflowError):
        return fallback


def _coerce_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return fallback
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "si", "sí"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
        return fallback
    if isinstance(value, (int, float)):
        try:
            return bool(value) if math.isfinite(float(value)) else fallback
        except (TypeError, ValueError, OverflowError):
            return fallback
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return fallback


def sanitize_audio_config(value: Any) -> Dict[str, Any]:
    """Normaliza configuraciones importadas o editadas a mano."""
    source = value if isinstance(value, dict) else {}
    device_id = str(source.get("device_id", "default") or "default").strip()[:1024]
    mode = str(source.get("profile_mute_mode", "keep") or "keep").strip().lower()
    if mode not in {"keep", "muted", "unmuted"}:
        mode = "keep"
    target_mode = str(
        source.get("target_mode", DEFAULT_TARGET_MODE) or DEFAULT_TARGET_MODE
    ).strip().lower()
    if target_mode not in TARGET_MODES:
        target_mode = DEFAULT_TARGET_MODE
    return {
        "enabled": _coerce_bool(source.get("enabled", True), True),
        "button_enabled": _coerce_bool(source.get("button_enabled", True), True),
        "target_mode": target_mode,
        "device_id": device_id or "default",
        "led_sync": _coerce_bool(source.get("led_sync", True), True),
        "apply_volume": _coerce_bool(source.get("apply_volume", False), False),
        "volume": _bounded_int(source.get("volume", 100), 0, 100, 100),
        "profile_mute_mode": mode,
    }


_DUALSENSE_NAME_TOKENS = (
    "dualsense",
    "wireless controller",
    "control inalámbrico",
    "control inalambrico",
    "controle sem fio",
)


def is_dualsense_audio_name(value: Any) -> bool:
    """Reconoce los nombres habituales del endpoint de audio del DualSense."""
    name = str(value or "").strip().casefold()
    return bool(name and any(token in name for token in _DUALSENSE_NAME_TOKENS))


def send_windows_microphone_mute_key() -> bool:
    """Emula la tecla física de silencio de micrófono de Windows.

    Windows representa las teclas multimedia especiales mediante
    ``WM_APPCOMMAND``. El comando 24 corresponde a la tecla de silencio del
    micrófono; no debe confundirse con ``VK_VOLUME_MUTE``, que silencia las
    bocinas. ``SendMessageTimeoutW`` evita que una aplicación colgada bloquee
    el hilo de audio de Nikaido.
    """
    if os.name != "nt":
        return False

    try:
        import ctypes
        from ctypes import wintypes

        wm_appcommand = 0x0319
        appcommand_microphone_volume_mute = 24
        smto_abortifhung = 0x0002
        timeout_ms = 250
        lparam = appcommand_microphone_volume_mute << 16

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetShellWindow.restype = wintypes.HWND
        user32.SendMessageTimeoutW.argtypes = (
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
            wintypes.UINT,
            wintypes.UINT,
            ctypes.POINTER(ctypes.c_size_t),
        )
        user32.SendMessageTimeoutW.restype = ctypes.c_size_t

        foreground = user32.GetForegroundWindow()
        shell = user32.GetShellWindow()
        targets = [foreground]
        if shell and shell != foreground:
            targets.append(shell)

        for hwnd in targets:
            if not hwnd:
                continue
            result = ctypes.c_size_t(0)
            delivered = user32.SendMessageTimeoutW(
                hwnd,
                wm_appcommand,
                hwnd,
                lparam,
                smto_abortifhung,
                timeout_ms,
                ctypes.byref(result),
            )
            if delivered:
                return True
    except Exception:
        logger.debug(
            "No se pudo enviar la tecla de silencio de micrófono de Windows",
            exc_info=True,
        )
    return False


class PycawCaptureBackend:
    """Adaptador pequeño alrededor de pycaw, cargado solo dentro de Windows."""

    DEVICE_CACHE_SECONDS = 4.0
    MISSING_DEVICE_RETRY_SECONDS = 3.0

    def __init__(self) -> None:
        self._AudioUtilities = None
        self._capture_flow = 1
        self._active_state = 1
        self._devices: list[Any] = []
        self._devices_at = 0.0
        self._missing_device_retry_at: Dict[str, float] = {}
        self._comtypes = None

    def initialize(self) -> None:
        if os.name != "nt":
            raise RuntimeError("El control de micrófono está disponible únicamente en Windows")

        try:
            import comtypes
            from pycaw.constants import DEVICE_STATE, EDataFlow
            from pycaw.pycaw import AudioUtilities
        except ModuleNotFoundError as exc:
            missing = str(getattr(exc, "name", "") or "dependencia de audio")
            runtime = str(Path(sys.executable).resolve())
            raise RuntimeError(
                f"Falta {missing} en el Python que abrió Nikaido ({runtime}). "
                "Cierra esta instancia y abre INICIAR_NIKAIDO.bat; ese iniciador "
                "usa y repara automáticamente el runtime corto de Nikaido."
            ) from exc

        # Este trabajador no necesita callbacks COM: un apartamento normal es
        # suficiente y evita depender del estado COM del hilo de Qt.
        comtypes.CoInitialize()
        self._comtypes = comtypes
        self._AudioUtilities = AudioUtilities
        self._capture_flow = int(getattr(EDataFlow.eCapture, "value", 1))
        self._active_state = int(getattr(DEVICE_STATE.ACTIVE, "value", 1))
        self._refresh_devices(force=True)

    def shutdown(self) -> None:
        # Suelta primero todos los wrappers COM. Mantener referencias después de
        # CoUninitialize puede dejar endpoints vivos hasta que termine Python y
        # complica reinicios del trabajador al cambiar/desconectar micrófonos.
        self._devices.clear()
        self._devices_at = 0.0
        self._missing_device_retry_at.clear()
        self._AudioUtilities = None
        comtypes_module = self._comtypes
        self._comtypes = None
        if comtypes_module is not None:
            try:
                comtypes_module.CoUninitialize()
            except Exception:
                pass

    def _as_audio_device(self, device: Any) -> Any:
        """Acepta tanto AudioDevice como el IMMDevice crudo de GetMicrophone()."""
        if device is None:
            return None
        if self._device_id(device) and hasattr(type(device), "EndpointVolume"):
            return device
        creator = getattr(self._AudioUtilities, "CreateDevice", None)
        if callable(creator):
            wrapped = creator(device)
            if wrapped is not None:
                return wrapped
        return device

    @staticmethod
    def _device_id(device: Any) -> str:
        return str(getattr(device, "id", getattr(device, "Id", "")) or "")

    @staticmethod
    def _device_name(device: Any) -> str:
        try:
            value = str(getattr(device, "FriendlyName", "") or "")
        except Exception:
            value = ""
        return value.strip()[:300] or "Micrófono sin nombre"

    def _default_device(self) -> Any:
        if self._AudioUtilities is None:
            raise RuntimeError("Pycaw no está inicializado")
        device = self._as_audio_device(self._AudioUtilities.GetMicrophone())
        if device is None or not self._device_id(device):
            raise RuntimeError("Windows no encontró un micrófono predeterminado")
        if not hasattr(type(device), "EndpointVolume") and not hasattr(device, "EndpointVolume"):
            raise RuntimeError("Pycaw devolvió un micrófono incompatible")
        return device

    def _refresh_devices(self, *, force: bool = False) -> list[Any]:
        if self._AudioUtilities is None:
            raise RuntimeError("Pycaw no está inicializado")
        now = time.monotonic()
        if not force and self._devices and now - self._devices_at < self.DEVICE_CACHE_SECONDS:
            return self._devices
        devices = self._AudioUtilities.GetAllDevices(
            data_flow=self._capture_flow,
            device_state=self._active_state,
        )
        self._devices = [
            wrapped
            for item in (devices or [])
            if (wrapped := self._as_audio_device(item)) is not None and self._device_id(wrapped)
        ]
        self._devices_at = now
        if force:
            available = {self._device_id(item) for item in self._devices}
            self._missing_device_retry_at = {
                key: deadline
                for key, deadline in self._missing_device_retry_at.items()
                if key not in available
            }
        return self._devices

    def list_capture_devices(self, *, force: bool = False) -> list[AudioDeviceInfo]:
        try:
            default = self._default_device()
        except Exception as exc:
            logger.debug("Windows no entregó un micrófono predeterminado: %s", exc)
            default = None
        default_id = self._device_id(default) if default is not None else ""
        devices = list(self._refresh_devices(force=force))
        if default is not None and default_id and all(
            self._device_id(item) != default_id for item in devices
        ):
            devices.insert(0, default)
        result = [
            AudioDeviceInfo(
                id=self._device_id(device),
                name=self._device_name(device),
                is_default=self._device_id(device) == default_id,
                is_dualsense=is_dualsense_audio_name(self._device_name(device)),
            )
            for device in devices
            if self._device_id(device)
        ]
        result.sort(
            key=lambda item: (not item.is_default, item.name.casefold(), item.id.casefold())
        )
        return result

    def _all_unique_devices(self, *, force: bool = False) -> list[Any]:
        devices = list(self._refresh_devices(force=force))
        try:
            default = self._default_device()
        except Exception as exc:
            logger.debug("No se pudo añadir el endpoint predeterminado al grupo: %s", exc)
            default = None
        default_id = self._device_id(default) if default is not None else ""
        if default is not None and default_id and all(
            self._device_id(item) != default_id for item in devices
        ):
            devices.insert(0, default)
        unique: Dict[str, Any] = {}
        for device in devices:
            device_id = self._device_id(device)
            if device_id and device_id not in unique:
                unique[device_id] = device
        return list(unique.values())

    def _group_devices(
        self, *, exclude_dualsense: bool = False, force: bool = False
    ) -> list[Any]:
        # Para escribir mute no reutilizamos wrappers COM viejos. Algunos
        # dispositivos Bluetooth/USB cambian su endpoint sin cambiar el nombre
        # y un objeto cacheado puede aceptar SetMute sin afectar al dispositivo
        # que Windows usa actualmente.
        devices = self._all_unique_devices(force=force)
        if exclude_dualsense:
            devices = [
                device
                for device in devices
                if not is_dualsense_audio_name(self._device_name(device))
            ]
        if not devices:
            if exclude_dualsense:
                raise RuntimeError(
                    "No hay micrófonos activos fuera del DualSense para controlar"
                )
            raise RuntimeError("Windows no encontró micrófonos activos")
        return devices

    def get_group_states(
        self, *, exclude_dualsense: bool = False
    ) -> list[AudioEndpointState]:
        return [
            self._state_from_device(device)
            for device in self._group_devices(exclude_dualsense=exclude_dualsense)
        ]

    def set_group_muted(
        self, muted: bool, *, exclude_dualsense: bool = False
    ) -> list[AudioEndpointState]:
        states: list[AudioEndpointState] = []
        errors: list[str] = []
        # Fuerza una enumeración nueva antes de escribir. Esto evita aplicar el
        # mute a un wrapper COM que quedó obsoleto después de reconectar USB,
        # Bluetooth, una webcam o unos audífonos.
        for device in self._group_devices(
            exclude_dualsense=exclude_dualsense, force=True
        ):
            try:
                states.append(self._set_device_muted_verified(device, muted))
            except Exception as exc:
                errors.append(f"{self._device_name(device)}: {exc}")
        if not states:
            detail = "; ".join(errors[:3]) or "ningún endpoint respondió"
            raise RuntimeError(f"No se pudo cambiar ningún micrófono: {detail}")
        if errors:
            logger.warning(
                "Mute global aplicado parcialmente (%s errores): %s",
                len(errors),
                "; ".join(errors[:3]),
            )
        return states

    def restore_group_mutes(self, muted_by_id: Dict[str, bool]) -> list[AudioEndpointState]:
        """Restaura solo endpoints que siguen presentes; nunca cae al predeterminado."""
        desired = {
            str(device_id): bool(muted)
            for device_id, muted in (muted_by_id or {}).items()
            if str(device_id)
        }
        states: list[AudioEndpointState] = []
        errors: list[str] = []
        for device in self._all_unique_devices(force=True):
            device_id = self._device_id(device)
            if device_id not in desired:
                continue
            try:
                states.append(
                    self._set_device_muted_verified(device, desired[device_id])
                )
            except Exception as exc:
                errors.append(f"{self._device_name(device)}: {exc}")
        if not states and desired:
            detail = "; ".join(errors[:3]) or "los dispositivos ya no están conectados"
            raise RuntimeError(f"No se pudo restaurar el mute anterior: {detail}")
        if errors:
            logger.warning(
                "Estado global restaurado parcialmente (%s errores): %s",
                len(errors),
                "; ".join(errors[:3]),
            )
        return states

    def _resolve_device(self, requested_id: str) -> Any:
        if not requested_id or requested_id == "default":
            return self._default_device()
        for device in self._refresh_devices():
            if self._device_id(device) == requested_id:
                self._missing_device_retry_at.pop(requested_id, None)
                return device
        now = time.monotonic()
        if now >= self._missing_device_retry_at.get(requested_id, 0.0):
            for device in self._refresh_devices(force=True):
                if self._device_id(device) == requested_id:
                    self._missing_device_retry_at.pop(requested_id, None)
                    return device
            self._missing_device_retry_at[requested_id] = now + self.MISSING_DEVICE_RETRY_SECONDS
        # Un perfil puede apuntar a unos audífonos desconectados. Caer al
        # predeterminado conserva el botón funcional sin borrar la preferencia.
        return self._default_device()

    def _state_from_device(
        self,
        device: Any,
        *,
        known_muted: Optional[bool] = None,
        fallback_volume: int = 100,
    ) -> AudioEndpointState:
        endpoint = device.EndpointVolume
        if known_muted is None:
            muted = bool(endpoint.GetMute())
        else:
            muted = bool(known_muted)
        try:
            scalar = float(endpoint.GetMasterVolumeLevelScalar())
            if not math.isfinite(scalar):
                raise ValueError("volumen no finito")
            volume = max(0, min(100, round(scalar * 100.0)))
        except Exception as exc:
            # Hay micrófonos (sobre todo Bluetooth y algunos drivers USB) que
            # exponen mute pero no volumen maestro. El mute sigue siendo válido;
            # no debemos marcar toda la operación como fallida por ese detalle.
            logger.debug(
                "El endpoint %s no expone volumen maestro: %s",
                self._device_name(device),
                exc,
            )
            volume = max(0, min(100, int(fallback_volume)))
        return AudioEndpointState(
            device_id=self._device_id(device),
            name=self._device_name(device),
            muted=muted,
            volume=volume,
        )

    def _set_device_muted_verified(
        self, device: Any, muted: bool
    ) -> AudioEndpointState:
        """Escribe y confirma el mute real del endpoint de captura.

        Algunos drivers aceptan SetMute antes de terminar de activar el endpoint.
        Reintentar brevemente y leer GetMute evita reportar éxito falso.
        """
        endpoint = device.EndpointVolume
        expected = bool(muted)
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                endpoint.SetMute(expected, None)
                # La mayoría responde inmediatamente; una pausa mínima ayuda a
                # endpoints Bluetooth que publican el cambio de forma asíncrona.
                if attempt:
                    time.sleep(0.025 * attempt)
                actual = bool(endpoint.GetMute())
                if actual == expected:
                    return self._state_from_device(
                        device, known_muted=actual
                    )
                last_error = RuntimeError(
                    f"Windows conservó mute={actual!s} después de solicitar {expected!s}"
                )
            except Exception as exc:
                last_error = exc
            if attempt < 2:
                time.sleep(0.035)
        raise RuntimeError(
            f"Windows no confirmó el cambio de mute: {last_error or 'estado sin respuesta'}"
        )

    def get_state(self, requested_id: str) -> AudioEndpointState:
        return self._state_from_device(self._resolve_device(requested_id))

    def set_muted(self, requested_id: str, muted: bool) -> AudioEndpointState:
        # Refrescar antes de una escritura evita usar un endpoint que quedó
        # cacheado tras cambiar el dispositivo predeterminado de Windows.
        if requested_id and requested_id != "default":
            self._refresh_devices(force=True)
        device = self._resolve_device(requested_id)
        return self._set_device_muted_verified(device, muted)

    def set_volume(self, requested_id: str, volume: int) -> AudioEndpointState:
        device = self._resolve_device(requested_id)
        scalar = max(0.0, min(1.0, int(volume) / 100.0))
        device.EndpointVolume.SetMasterVolumeLevelScalar(scalar, None)
        return self._state_from_device(device)


@dataclass
class _Command:
    name: str
    value: Any = None
    done: Optional[threading.Event] = None
    result: Optional[dict] = None


class AudioManager:
    """Sincroniza Windows, el botón MIC, el LED naranja y los perfiles."""

    POLL_INTERVAL = 0.35
    RETRY_INTERVAL = 5.0
    BUTTON_DEBOUNCE_SECONDS = 0.22

    def __init__(
        self,
        connection_manager: Any = None,
        config: Any = None,
        *,
        backend_factory: Optional[Callable[[], Any]] = None,
        microphone_key_sender: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.connection_manager = connection_manager
        self._backend_factory = backend_factory or PycawCaptureBackend
        self._microphone_key_sender = (
            microphone_key_sender or send_windows_microphone_mute_key
        )
        self._config = sanitize_audio_config(config)
        self._profile_id = ""
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()
        self._commands: queue.Queue[_Command] = queue.Queue(maxsize=128)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._stopping = False
        self._last_button = False
        self._last_button_edge = 0.0
        self._last_controller_muted: Optional[bool] = None
        self._last_controller_led_sync: Optional[bool] = None
        self._group_restore_mutes: Dict[str, bool] = {}
        self._group_restore_key = ""
        self._snapshot: Dict[str, Any] = {
            "running": False,
            "available": False,
            "error": "Esperando al motor de audio",
            "profile_id": "",
            "selected_device_id": self._config["device_id"],
            "target_mode": self._config["target_mode"],
            "active_device_id": "",
            "device_name": "—",
            "using_fallback": False,
            "muted": False,
            "partially_muted": False,
            "target_count": 0,
            "muted_count": 0,
            "restore_pending": False,
            "volume": self._config["volume"],
            "devices": [],
            "enabled": self._config["enabled"],
            "button_enabled": self._config["button_enabled"],
            "led_sync": self._config["led_sync"],
            "keyboard_mic_key_sent": False,
            "last_button_action": "",
            "updated_at": 0.0,
        }

        if connection_manager is not None:
            on_state = getattr(connection_manager, "on_state_update", None)
            if callable(on_state):
                on_state(self._on_controller_state)
            on_connect = getattr(connection_manager, "on_connect", None)
            if callable(on_connect):
                on_connect(self._on_controller_connect)
            on_disconnect = getattr(connection_manager, "on_disconnect", None)
            if callable(on_disconnect):
                on_disconnect(self._on_controller_disconnect)

    def start(self) -> bool:
        with self._lifecycle_lock:
            if self._running or self._stopping:
                return self._running
            thread = self._thread
            if thread is not None and thread.is_alive():
                logger.warning("AudioManager no se reinició: el trabajador anterior sigue vivo")
                return False
            self._thread = None
            self._stop_event.clear()
            self._running = True
            self._thread = threading.Thread(
                target=self._worker,
                name="WindowsAudioManager",
                daemon=True,
            )
            self._thread.start()
        return True

    def stop(self) -> None:
        with self._lifecycle_lock:
            if self._stopping:
                return
            self._stopping = True
            self._running = False
            self._stop_event.set()
            thread = self._thread
            try:
                self._commands.put_nowait(_Command("stop"))
            except queue.Full:
                pass
        if thread and thread is not threading.current_thread() and thread.is_alive():
            thread.join(timeout=3.0)
        with self._lifecycle_lock:
            stopped = thread is None or not thread.is_alive()
            if self._thread is thread and stopped:
                self._thread = None
            if stopped:
                self._discard_pending_commands("AudioManager detenido")
            self._stopping = False
        self._sync_controller(False, False, force=True)
        self._update_snapshot(running=False)

    def get_config(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._config)

    def apply_config(
        self,
        config: Any,
        profile_id: str = "",
        *,
        apply_profile_state: bool = True,
    ) -> Dict[str, Any]:
        """Aplica opciones; los cambios de edición pueden omitir acciones del perfil."""
        normalized = sanitize_audio_config(config)
        restore_before_switch: Dict[str, bool] = {}
        restore_key = ""
        with self._lock:
            previous_key = self._target_key(self._config)
            next_key = self._target_key(normalized)
            target_changed = previous_key != next_key
            if target_changed:
                if (
                    self._group_restore_key == previous_key
                    and self._group_restore_mutes
                ):
                    restore_before_switch = dict(self._group_restore_mutes)
                    restore_key = self._group_restore_key
                elif not self._running:
                    self._group_restore_mutes.clear()
                    self._group_restore_key = ""
            self._config = normalized
            self._profile_id = str(profile_id or "")[:120]
            self._snapshot.update(
                {
                    "profile_id": self._profile_id,
                    "selected_device_id": normalized["device_id"],
                    "target_mode": normalized["target_mode"],
                    "enabled": normalized["enabled"],
                    "button_enabled": normalized["button_enabled"],
                    "led_sync": normalized["led_sync"],
                    "restore_pending": False if target_changed else bool(
                        self._snapshot.get("restore_pending", False)
                    ),
                }
            )
        if self._running:
            self._enqueue(
                "apply_config",
                {
                    "config": copy.deepcopy(normalized),
                    "apply_profile_state": bool(apply_profile_state),
                    "restore_before_switch": restore_before_switch,
                    "restore_key": restore_key,
                },
            )
        return copy.deepcopy(normalized)

    @staticmethod
    def _target_key(config: Dict[str, Any]) -> str:
        mode = str(config.get("target_mode", DEFAULT_TARGET_MODE) or DEFAULT_TARGET_MODE)
        if mode == "selected":
            return f"selected:{config.get('device_id', 'default')}"
        return mode

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._snapshot)

    def get_devices(self) -> list[Dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._snapshot.get("devices", []))

    def refresh_devices(self, *, wait: bool = False, timeout: float = 2.0) -> list[Dict[str, Any]]:
        command = self._enqueue("refresh_devices", True, wait=wait, timeout=timeout)
        if command and command.result and "devices" in command.result:
            return copy.deepcopy(command.result["devices"])
        return self.get_devices()

    def refresh_state(self) -> None:
        self._enqueue("refresh_state")

    def toggle_mute(self, *, source: str = "api") -> None:
        normalized_source = "controller" if source == "controller" else "api"
        self._enqueue("toggle_mute", {"source": normalized_source})

    def set_muted(self, muted: bool) -> None:
        self._enqueue("set_muted", bool(muted))

    def set_volume(self, volume: Any) -> None:
        self._enqueue("set_volume", _bounded_int(volume, 0, 100, 100))

    def _enqueue(
        self,
        name: str,
        value: Any = None,
        *,
        wait: bool = False,
        timeout: float = 2.0,
    ) -> Optional[_Command]:
        if not self._running and name != "apply_config":
            return None
        done = threading.Event() if wait else None
        command = _Command(name=name, value=value, done=done, result={})
        try:
            self._commands.put_nowait(command)
        except queue.Full:
            logger.warning("Se descartó una orden de audio por saturación: %s", name)
            return None
        if done is not None:
            done.wait(max(0.05, float(timeout)))
        return command

    def _discard_pending_commands(self, error: str) -> None:
        while True:
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                return
            if command.result is not None:
                command.result["error"] = error
            if command.done is not None:
                command.done.set()

    def _on_controller_state(self, state: Any) -> None:
        buttons = getattr(state, "buttons", {}) or {}
        pressed = bool(buttons.get("mute", False)) if isinstance(buttons, dict) else False
        now = time.monotonic()
        with self._lock:
            enabled = bool(self._config.get("enabled", True))
            button_enabled = bool(self._config.get("button_enabled", True))
            rising = pressed and not self._last_button
            self._last_button = pressed
            debounce_ok = now - self._last_button_edge >= self.BUTTON_DEBOUNCE_SECONDS
            if rising and debounce_ok:
                self._last_button_edge = now
        if enabled and button_enabled and rising and debounce_ok:
            self.toggle_mute(source="controller")

    def _on_controller_connect(self, _connection: Any) -> None:
        with self._lock:
            self._last_button = False
            muted = bool(self._snapshot.get("muted", False))
            led_sync = bool(
                self._config.get("enabled", True) and self._config.get("led_sync", True)
            )
        self._sync_controller(muted, led_sync, force=True)

    def _on_controller_disconnect(self) -> None:
        with self._lock:
            self._last_button = False
            self._last_controller_muted = None
            self._last_controller_led_sync = None

    def _update_snapshot(self, **changes: Any) -> None:
        with self._lock:
            self._snapshot.update(changes)
            self._snapshot["updated_at"] = time.time()

    def _publish_devices(self, devices: Iterable[AudioDeviceInfo]) -> list[Dict[str, Any]]:
        payload = [asdict(item) for item in devices]
        self._update_snapshot(devices=payload)
        return payload

    def _publish_endpoint(self, state: AudioEndpointState, *, force_led: bool = False) -> None:
        with self._lock:
            selected_id = str(self._config.get("device_id", "default") or "default")
            led_sync = bool(
                self._config.get("enabled", True) and self._config.get("led_sync", True)
            )
        self._update_snapshot(
            available=True,
            error="",
            active_device_id=state.device_id,
            device_name=state.name,
            using_fallback=bool(
                selected_id not in {"", "default"} and state.device_id != selected_id
            ),
            muted=bool(state.muted),
            partially_muted=False,
            target_count=1,
            muted_count=1 if state.muted else 0,
            restore_pending=False,
            volume=_bounded_int(state.volume, 0, 100, 100),
        )
        self._sync_controller(bool(state.muted), led_sync, force=force_led)

    def _publish_group(
        self,
        states: Iterable[AudioEndpointState],
        *,
        target_mode: str,
        force_led: bool = False,
    ) -> None:
        items = list(states)
        if not items:
            raise RuntimeError("No hay micrófonos activos para controlar")
        muted_count = sum(1 for state in items if state.muted)
        all_muted = muted_count == len(items)
        any_muted = muted_count > 0
        if target_mode == "all_except_dualsense":
            name = f"Todos excepto DualSense ({len(items)})"
        else:
            name = f"Todos los micrófonos ({len(items)})"
        average_volume = round(sum(state.volume for state in items) / len(items))
        with self._lock:
            led_sync = bool(
                self._config.get("enabled", True) and self._config.get("led_sync", True)
            )
            restore_pending = bool(
                self._group_restore_mutes
                and self._group_restore_key == self._target_key(self._config)
            )
        self._update_snapshot(
            available=True,
            error="",
            active_device_id=target_mode,
            device_name=name,
            using_fallback=False,
            muted=all_muted,
            partially_muted=bool(any_muted and not all_muted),
            target_count=len(items),
            muted_count=muted_count,
            restore_pending=restore_pending,
            volume=max(0, min(100, average_volume)),
        )
        self._sync_controller(all_muted, led_sync, force=force_led)

    def _sync_controller(self, muted: bool, led_sync: bool, *, force: bool = False) -> None:
        manager = self.connection_manager
        if manager is None:
            return
        with self._lock:
            if (
                not force
                and self._last_controller_muted is muted
                and self._last_controller_led_sync is led_sync
            ):
                return
        setter = getattr(manager, "set_microphone_state", None)
        if not callable(setter):
            return
        target = muted if led_sync else False
        with self._lock:
            target_mode = str(self._config.get("target_mode", DEFAULT_TARGET_MODE) or DEFAULT_TARGET_MODE)
        mute_controller_audio = target_mode != "all_except_dualsense"
        try:
            # Al desactivar la sincronización también restauramos el
            # micrófono interno del control a activo; de otro modo podría
            # quedar físicamente muteado con el LED apagado.
            result = setter(target, mute_audio=mute_controller_audio)
        except TypeError:
            try:
                result = setter(target)
            except Exception:
                logger.debug("No se pudo sincronizar el LED MIC del DualSense", exc_info=True)
                return
        except Exception:
            logger.debug("No se pudo sincronizar el LED MIC del DualSense", exc_info=True)
            return
        if result is False:
            return
        with self._lock:
            self._last_controller_muted = muted
            self._last_controller_led_sync = led_sync

    @staticmethod
    def _is_group_mode(target_mode: str) -> bool:
        return target_mode in {"all", "all_except_dualsense"}

    @staticmethod
    def _exclude_dualsense(target_mode: str) -> bool:
        return target_mode == "all_except_dualsense"

    def _read_target(
        self,
        backend: Any,
        config: Dict[str, Any],
        *,
        force_led: bool = False,
    ) -> None:
        target_mode = str(config.get("target_mode", DEFAULT_TARGET_MODE) or DEFAULT_TARGET_MODE)
        if not self._is_group_mode(target_mode):
            self._publish_endpoint(
                backend.get_state(str(config.get("device_id", "default"))),
                force_led=force_led,
            )
            return
        getter = getattr(backend, "get_group_states", None)
        if not callable(getter):
            raise RuntimeError("El backend de audio no soporta mute global")
        states = list(getter(exclude_dualsense=self._exclude_dualsense(target_mode)))
        with self._lock:
            restore_active = bool(
                self._group_restore_mutes
                and self._group_restore_key == self._target_key(config)
            )
        if restore_active and any(not state.muted for state in states):
            # Un dispositivo conectado después del mute, o reactivado desde
            # Windows, sigue formando parte de la sesión global activa.
            self._set_group_target_muted(
                backend, config, True, force_led=force_led
            )
            return
        self._publish_group(states, target_mode=target_mode, force_led=force_led)

    def _set_group_target_muted(
        self,
        backend: Any,
        config: Dict[str, Any],
        muted: bool,
        *,
        force_led: bool = True,
    ) -> None:
        target_mode = str(config.get("target_mode", "all") or "all")
        exclude = self._exclude_dualsense(target_mode)
        getter = getattr(backend, "get_group_states", None)
        setter = getattr(backend, "set_group_muted", None)
        restorer = getattr(backend, "restore_group_mutes", None)
        if not callable(getter) or not callable(setter):
            raise RuntimeError("El backend de audio no soporta mute global")

        target_key = self._target_key(config)
        if muted:
            before = list(getter(exclude_dualsense=exclude))
            already_muted = bool(before) and all(state.muted for state in before)
            if not already_muted:
                with self._lock:
                    if self._group_restore_key == target_key and self._group_restore_mutes:
                        for state in before:
                            self._group_restore_mutes.setdefault(
                                state.device_id, bool(state.muted)
                            )
                    else:
                        self._group_restore_mutes = {
                            state.device_id: bool(state.muted) for state in before
                        }
                    self._group_restore_key = target_key
                states = setter(True, exclude_dualsense=exclude)
            else:
                # Aplicar de nuevo un perfil ya silenciado no debe reemplazar
                # la restauración original por un mapa donde todo era True.
                states = before
        else:
            with self._lock:
                can_restore = bool(
                    self._group_restore_mutes and self._group_restore_key == target_key
                )
                restore_map = dict(self._group_restore_mutes) if can_restore else {}
            if restore_map and callable(restorer):
                restorer(restore_map)
                states = list(getter(exclude_dualsense=exclude))
            else:
                states = setter(False, exclude_dualsense=exclude)
            with self._lock:
                if self._group_restore_key == target_key:
                    self._group_restore_mutes.clear()
                    self._group_restore_key = ""
        self._publish_group(states, target_mode=target_mode, force_led=force_led)

    def _worker(self) -> None:
        backend = None
        next_poll = 0.0
        next_retry = 0.0
        self._update_snapshot(running=True)
        try:
            while not self._stop_event.is_set():
                now = time.monotonic()
                if backend is None and now >= next_retry:
                    candidate = None
                    try:
                        candidate = self._backend_factory()
                        candidate.initialize()
                        if self._stop_event.is_set():
                            candidate.shutdown()
                            candidate = None
                            break
                        devices = candidate.list_capture_devices(force=True)
                        if self._stop_event.is_set():
                            candidate.shutdown()
                            candidate = None
                            break
                        backend = candidate
                        self._publish_devices(devices)
                        self._update_snapshot(available=True, error="")
                        with self._lock:
                            initial_config = copy.deepcopy(self._config)
                        self._apply_config_to_backend(
                            backend, initial_config, apply_profile_state=True
                        )
                        next_poll = time.monotonic() + self.POLL_INTERVAL
                    except Exception as exc:
                        if candidate is not None:
                            try:
                                candidate.shutdown()
                            except Exception:
                                pass
                        backend = None
                        next_retry = now + self.RETRY_INTERVAL
                        self._update_snapshot(
                            available=False,
                            error=f"{type(exc).__name__}: {exc}",
                        )

                timeout = 0.15
                if backend is not None and next_poll:
                    timeout = max(0.02, min(timeout, next_poll - now))
                try:
                    command = self._commands.get(timeout=max(0.02, timeout))
                except queue.Empty:
                    command = None

                if command is not None:
                    try:
                        if command.name == "stop":
                            break
                        if backend is None:
                            if self._execute_keyboard_only_toggle(command):
                                continue
                            raise RuntimeError(
                                self.get_snapshot().get("error") or "Audio no disponible"
                            )
                        self._execute_command(backend, command)
                    except Exception as exc:
                        logger.warning("Falló la orden de audio %s: %s", command.name, exc)
                        self._update_snapshot(
                            available=False,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                        # Errores de dispositivo suelen resolverse reabriendo COM.
                        try:
                            backend.shutdown()
                        except Exception:
                            pass
                        backend = None
                        next_retry = time.monotonic() + self.RETRY_INTERVAL
                    finally:
                        if command.done is not None:
                            command.done.set()

                now = time.monotonic()
                if backend is not None and now >= next_poll:
                    try:
                        with self._lock:
                            enabled = bool(self._config.get("enabled", True))
                            current_config = copy.deepcopy(self._config)
                        if enabled:
                            self._read_target(backend, current_config)
                        next_poll = now + self.POLL_INTERVAL
                    except Exception as exc:
                        logger.debug("No se pudo actualizar el micrófono: %s", exc)
                        self._update_snapshot(
                            available=False,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                        try:
                            backend.shutdown()
                        except Exception:
                            pass
                        backend = None
                        next_retry = now + self.RETRY_INTERVAL
        finally:
            if backend is not None:
                try:
                    backend.shutdown()
                except Exception:
                    pass
            # Si stop() agotó su espera mientras Core Audio estaba bloqueado,
            # este finally es la última autoridad: ningún trabajador tardío
            # puede dejar el MIC/LED encendido después de cerrar Nikaido.
            self._sync_controller(False, False, force=True)
            with self._lifecycle_lock:
                if self._thread is threading.current_thread():
                    self._running = False
            self._update_snapshot(running=False)

    def _apply_config_to_backend(
        self,
        backend: Any,
        incoming: Dict[str, Any],
        *,
        apply_profile_state: bool,
    ) -> None:
        device_id = incoming["device_id"]
        target_mode = incoming["target_mode"]
        if (
            apply_profile_state
            and incoming["apply_volume"]
            and target_mode == "selected"
        ):
            self._publish_endpoint(backend.set_volume(device_id, incoming["volume"]))
        mode = incoming["profile_mute_mode"] if apply_profile_state else "keep"
        if mode == "muted":
            if self._is_group_mode(target_mode):
                self._set_group_target_muted(backend, incoming, True)
            else:
                self._publish_endpoint(backend.set_muted(device_id, True), force_led=True)
        elif mode == "unmuted":
            if self._is_group_mode(target_mode):
                self._set_group_target_muted(backend, incoming, False)
            else:
                self._publish_endpoint(backend.set_muted(device_id, False), force_led=True)
        else:
            self._read_target(backend, incoming, force_led=True)

    def _send_controller_microphone_key(
        self,
        *,
        target_muted: bool,
        led_sync: bool,
    ) -> bool:
        """Envía la tecla MIC de Windows y adelanta el LED del DualSense."""
        try:
            sent = bool(self._microphone_key_sender())
        except Exception:
            logger.debug(
                "Falló el emulador de la tecla MIC de Windows",
                exc_info=True,
            )
            sent = False
        self._update_snapshot(
            keyboard_mic_key_sent=sent,
            last_button_action=(
                "windows_microphone_mute_key" if sent else "direct_audio"
            ),
        )
        if sent:
            # La orden de teclado no expone un estado de retorno. Encendemos o
            # apagamos el LED con el estado que Nikaido está a punto de forzar
            # mediante Core Audio; la lectura posterior confirma el resultado.
            self._sync_controller(bool(target_muted), bool(led_sync), force=True)
        return sent

    def _execute_keyboard_only_toggle(self, command: _Command) -> bool:
        """Usa la tecla MIC aunque Core Audio todavía no esté disponible."""
        if command.name != "toggle_mute":
            return False
        payload = command.value if isinstance(command.value, dict) else {}
        if str(payload.get("source", "api") or "api") != "controller":
            return False

        with self._lock:
            config = copy.deepcopy(self._config)
            current_muted = bool(self._snapshot.get("muted", False))
            partially_muted = bool(self._snapshot.get("partially_muted", False))
        if str(config.get("target_mode", DEFAULT_TARGET_MODE) or DEFAULT_TARGET_MODE) != "all":
            return False

        target_muted = True if partially_muted else not current_muted
        led_sync = bool(config.get("enabled", True) and config.get("led_sync", True))
        if not self._send_controller_microphone_key(
            target_muted=target_muted,
            led_sync=led_sync,
        ):
            return False

        self._update_snapshot(
            available=True,
            error=(
                "Core Audio no está disponible; se usó la tecla MIC de Windows "
                "sin poder confirmar todos los dispositivos."
            ),
            active_device_id="windows-microphone-mute-key",
            device_name="Tecla MIC de Windows (sin verificación)",
            using_fallback=True,
            muted=target_muted,
            partially_muted=False,
            muted_count=0,
            target_count=0,
            restore_pending=False,
        )
        return True

    def _execute_command(self, backend: Any, command: _Command) -> None:
        with self._lock:
            config = copy.deepcopy(self._config)
        device_id = str(config.get("device_id", "default"))
        target_mode = str(config.get("target_mode", DEFAULT_TARGET_MODE) or DEFAULT_TARGET_MODE)
        if command.name == "refresh_devices":
            devices = self._publish_devices(backend.list_capture_devices(force=bool(command.value)))
            if command.result is not None:
                command.result["devices"] = devices
            self._read_target(backend, config, force_led=True)
        elif command.name == "refresh_state":
            self._read_target(backend, config, force_led=True)
        elif command.name == "toggle_mute":
            if self._is_group_mode(target_mode):
                getter = getattr(backend, "get_group_states", None)
                if not callable(getter):
                    raise RuntimeError("El backend de audio no soporta mute global")
                states = list(
                    getter(exclude_dualsense=self._exclude_dualsense(target_mode))
                )
                all_muted = bool(states) and all(state.muted for state in states)
                target_muted = not all_muted
                payload = command.value if isinstance(command.value, dict) else {}
                source = str(payload.get("source", "api") or "api")
                use_keyboard_key = source == "controller" and target_mode == "all"

                if use_keyboard_key and target_muted:
                    # Guardamos el estado original ANTES de enviar la tecla. La
                    # propia orden de Windows puede cambiar el micrófono
                    # predeterminado y no queremos restaurarlo luego como si ya
                    # hubiera estado silenciado desde el principio.
                    target_key = self._target_key(config)
                    with self._lock:
                        if not (
                            self._group_restore_key == target_key
                            and self._group_restore_mutes
                        ):
                            self._group_restore_mutes = {
                                state.device_id: bool(state.muted) for state in states
                            }
                            self._group_restore_key = target_key

                if use_keyboard_key:
                    with self._lock:
                        led_sync = bool(
                            self._config.get("enabled", True)
                            and self._config.get("led_sync", True)
                        )
                    self._send_controller_microphone_key(
                        target_muted=target_muted,
                        led_sync=led_sync,
                    )
                else:
                    self._update_snapshot(
                        keyboard_mic_key_sent=False,
                        last_button_action="direct_audio",
                    )

                self._set_group_target_muted(backend, config, target_muted)
            else:
                self._update_snapshot(
                    keyboard_mic_key_sent=False,
                    last_button_action="direct_audio",
                )
                state = backend.get_state(device_id)
                self._publish_endpoint(
                    backend.set_muted(device_id, not state.muted), force_led=True
                )
        elif command.name == "set_muted":
            if self._is_group_mode(target_mode):
                self._set_group_target_muted(
                    backend, config, bool(command.value), force_led=True
                )
            else:
                self._publish_endpoint(
                    backend.set_muted(device_id, bool(command.value)), force_led=True
                )
        elif command.name == "set_volume":
            if self._is_group_mode(target_mode):
                # Un QTimer antiguo puede dispararse justo después de cambiar
                # el alcance a global. Ignorarlo evita reiniciar Core Audio por
                # una orden que ya dejó de aplicar.
                self._read_target(backend, config)
                return
            self._publish_endpoint(backend.set_volume(device_id, int(command.value)))
        elif command.name == "apply_config":
            payload = command.value if isinstance(command.value, dict) else {}
            restore_map = payload.get("restore_before_switch")
            restore_key = str(payload.get("restore_key", "") or "")
            if isinstance(restore_map, dict) and restore_map:
                restorer = getattr(backend, "restore_group_mutes", None)
                if callable(restorer):
                    try:
                        restorer(restore_map)
                    except Exception as exc:
                        logger.warning(
                            "No se pudo restaurar el mute global antes de cambiar alcance: %s",
                            exc,
                        )
                with self._lock:
                    if self._group_restore_key == restore_key:
                        self._group_restore_mutes.clear()
                        self._group_restore_key = ""
            if isinstance(payload.get("config"), dict):
                incoming = sanitize_audio_config(payload["config"])
                apply_profile_state = bool(payload.get("apply_profile_state", True))
            else:
                # Compatibilidad con órdenes creadas por builds anteriores.
                incoming = sanitize_audio_config(payload)
                apply_profile_state = True
            self._apply_config_to_backend(
                backend, incoming, apply_profile_state=apply_profile_state
            )
        else:
            raise ValueError(f"Orden de audio desconocida: {command.name}")
