"""Actualizaciones verificadas para la edición independiente de Nikaido.

El motor no depende de Qt. Puede consultarse desde pruebas o ejecutarse en un
hilo mediante ``check_async`` / ``download_async``. La edición de Steam puede
anularlo con ``NIKAIDO_DISTRIBUTION=steam``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from nikaido_version import APP_NAME, APP_VERSION, UPDATE_MANIFEST_URL

logger = logging.getLogger(__name__)

MAX_MANIFEST_BYTES = 512 * 1024
MAX_INSTALLER_BYTES = 600 * 1024 * 1024
DEFAULT_TIMEOUT = 15.0


class UpdateError(RuntimeError):
    """Fallo controlado durante consulta, validación, descarga o ejecución."""


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    title: str
    notes: str
    download_url: str
    sha256: str
    size_bytes: int
    channel: str = "stable"
    silent_args: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "title": self.title,
            "notes": self.notes,
            "download_url": self.download_url,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "channel": self.channel,
            "silent_args": list(self.silent_args),
        }


@dataclass(frozen=True)
class UpdateCheckResult:
    status: str
    current_version: str
    update: Optional[UpdateInfo] = None
    message: str = ""

    @property
    def available(self) -> bool:
        return self.status == "available" and self.update is not None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "current_version": self.current_version,
            "update": self.update.as_dict() if self.update else None,
            "message": self.message,
        }


def _version_key(value: Any) -> tuple[tuple[int, ...], int, int]:
    """Compara versiones numéricas y reconoce sufijos beta/rc sin dependencias."""
    text = str(value or "0").strip().lower().lstrip("v")
    numbers = tuple(int(part) for part in re.findall(r"\d+", text)[:4])
    numbers = numbers + (0,) * (4 - len(numbers))
    if "dev" in text or "alpha" in text:
        stage = 0
    elif "beta" in text or re.search(r"(?:^|[.-])b\d*", text):
        stage = 1
    elif "rc" in text:
        stage = 2
    else:
        stage = 3
    suffix = re.findall(r"(?:dev|alpha|beta|rc|b)[.-]?(\d+)", text)
    return numbers, stage, int(suffix[-1]) if suffix else 0


def is_newer_version(candidate: Any, current: Any = APP_VERSION) -> bool:
    return _version_key(candidate) > _version_key(current)


def _safe_url(url: str, *, allow_file: bool = False) -> str:
    parsed = urllib.parse.urlparse(str(url or "").strip())
    scheme = parsed.scheme.lower()
    localhost = (parsed.hostname or "").lower() in {"localhost", "127.0.0.1", "::1"}
    if scheme == "https" or (scheme == "http" and localhost):
        return parsed.geturl()
    if allow_file and scheme == "file":
        return parsed.geturl()
    raise UpdateError("La dirección de actualización debe usar HTTPS")


def _read_response(response: Any, *, maximum: int) -> bytes:
    expected = response.headers.get("Content-Length") if hasattr(response, "headers") else None
    if expected:
        try:
            if int(expected) > maximum:
                raise UpdateError("El archivo de actualización supera el tamaño permitido")
        except ValueError:
            pass
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(1024 * 1024, maximum + 1 - total))
        if not chunk:
            break
        total += len(chunk)
        if total > maximum:
            raise UpdateError("El archivo de actualización supera el tamaño permitido")
        chunks.append(chunk)
    return b"".join(chunks)


def parse_manifest(payload: Mapping[str, Any], *, channel: str = "stable") -> UpdateInfo:
    if not isinstance(payload, Mapping):
        raise UpdateError("El manifiesto de actualización no es válido")
    product = str(payload.get("product") or APP_NAME).strip()
    if product.casefold() != APP_NAME.casefold():
        raise UpdateError("El manifiesto pertenece a otro producto")
    release_channel = str(payload.get("channel") or "stable").strip().lower()
    requested = str(channel or "stable").strip().lower()
    if requested == "stable" and release_channel not in {"stable", "release"}:
        raise UpdateError("La versión encontrada pertenece al canal beta")

    version = str(payload.get("version") or "").strip().lstrip("v")
    title = str(payload.get("title") or f"Nikaido {version}").strip()[:180]
    notes = str(payload.get("notes") or "").strip()[:24_000]
    download_url = _safe_url(str(payload.get("download_url") or ""), allow_file=True)
    sha256 = str(payload.get("sha256") or "").strip().lower()
    try:
        size_bytes = int(payload.get("size_bytes") or 0)
    except (TypeError, ValueError, OverflowError) as exc:
        raise UpdateError("El tamaño del instalador no es válido") from exc
    raw_args = payload.get("silent_args") or []
    if not isinstance(raw_args, list):
        raw_args = []
    allowed_args = {
        "/SP-", "/SILENT", "/VERYSILENT", "/CLOSEAPPLICATIONS",
        "/RESTARTAPPLICATIONS", "/NORESTART",
    }
    silent_args = tuple(
        str(item).strip().upper()
        for item in raw_args[:12]
        if str(item).strip().upper() in allowed_args
    )

    if not re.fullmatch(r"\d+(?:\.\d+){1,3}(?:[-._]?(?:beta|rc|alpha|b)\d*)?", version, re.I):
        raise UpdateError("La versión del manifiesto no es válida")
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise UpdateError("Falta una firma SHA-256 válida para el instalador")
    if size_bytes <= 0 or size_bytes > MAX_INSTALLER_BYTES:
        raise UpdateError("El tamaño del instalador está fuera del límite permitido")
    return UpdateInfo(
        version=version,
        title=title,
        notes=notes,
        download_url=download_url,
        sha256=sha256,
        size_bytes=size_bytes,
        channel=release_channel,
        silent_args=silent_args,
    )


class UpdateManager:
    def __init__(
        self,
        profile_manager: Any = None,
        *,
        current_version: str = APP_VERSION,
        manifest_url: str = UPDATE_MANIFEST_URL,
        opener: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.profile_manager = profile_manager
        self.current_version = str(current_version)
        self.default_manifest_url = str(manifest_url or "")
        self._opener = opener or urllib.request.urlopen
        self._lock = threading.RLock()
        self._last_check_at = 0.0
        self._last_result = UpdateCheckResult("idle", self.current_version)
        self._downloaded_path = ""

    @property
    def distribution(self) -> str:
        return str(os.environ.get("NIKAIDO_DISTRIBUTION", "standalone") or "standalone").lower()

    def setting(self, key: str, default: Any = None) -> Any:
        if self.profile_manager is None:
            return default
        return self.profile_manager.get_setting(f"updates.{key}", default)

    def set_setting(self, key: str, value: Any) -> None:
        if self.profile_manager is not None:
            self.profile_manager.set_setting(f"updates.{key}", value)

    def manifest_url(self) -> str:
        env = str(os.environ.get("NIKAIDO_UPDATE_MANIFEST_URL", "") or "").strip()
        configured = str(self.setting("manifest_url", "") or "").strip()
        return env or configured or self.default_manifest_url.strip()

    def channel(self) -> str:
        value = str(self.setting("channel", "stable") or "stable").strip().lower()
        return value if value in {"stable", "beta"} else "stable"

    def should_auto_check(self) -> bool:
        if self.distribution == "steam":
            return False
        if not bool(self.setting("check_on_startup", True)):
            return False
        if not self.manifest_url():
            return False
        try:
            hours = int(self.setting("check_interval_hours", 24) or 24)
        except (TypeError, ValueError, OverflowError):
            hours = 24
        hours = max(1, min(168, hours))
        try:
            last = float(self.setting("last_check_unix", 0.0) or 0.0)
        except (TypeError, ValueError, OverflowError):
            last = 0.0
        return time.time() - last >= hours * 3600

    def check(self) -> UpdateCheckResult:
        if self.distribution == "steam":
            result = UpdateCheckResult(
                "managed_externally", self.current_version, message="Steam administra esta edición"
            )
            self._remember_result(result)
            return result
        url = self.manifest_url()
        if not url:
            result = UpdateCheckResult(
                "unconfigured",
                self.current_version,
                message="Servidor de actualizaciones aún no configurado",
            )
            self._remember_result(result)
            return result
        try:
            safe_url = _safe_url(url, allow_file=True)
            request = urllib.request.Request(
                safe_url,
                headers={"User-Agent": f"{APP_NAME.replace(' ', '-')}/{self.current_version}"},
            )
            with self._opener(request, timeout=DEFAULT_TIMEOUT) as response:
                final_url = getattr(response, "geturl", lambda: safe_url)()
                _safe_url(str(final_url or safe_url), allow_file=True)
                data = _read_response(response, maximum=MAX_MANIFEST_BYTES)
            payload = json.loads(data.decode("utf-8-sig"))
            info = parse_manifest(payload, channel=self.channel())
            skipped = str(self.setting("skipped_version", "") or "")
            if is_newer_version(info.version, self.current_version) and info.version != skipped:
                result = UpdateCheckResult("available", self.current_version, info, "Actualización disponible")
            elif info.version == skipped and is_newer_version(info.version, self.current_version):
                result = UpdateCheckResult("skipped", self.current_version, info, "Versión omitida")
            else:
                result = UpdateCheckResult("current", self.current_version, message="Nikaido está actualizado")
        except (UpdateError, urllib.error.URLError, OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
            message = str(getattr(exc, "reason", exc) or type(exc).__name__)
            result = UpdateCheckResult("error", self.current_version, message=message[:300])
        self.set_setting("last_check_unix", time.time())
        self._remember_result(result)
        return result

    def _remember_result(self, result: UpdateCheckResult) -> None:
        with self._lock:
            self._last_check_at = time.time()
            self._last_result = result

    def check_async(self, callback: Callable[[UpdateCheckResult], None]) -> threading.Thread:
        def worker() -> None:
            result = self.check()
            try:
                callback(result)
            except Exception:
                logger.exception("Callback de actualización falló")

        thread = threading.Thread(target=worker, name="NikaidoUpdateCheck", daemon=True)
        thread.start()
        return thread

    def download(
        self,
        info: UpdateInfo,
        *,
        progress: Optional[Callable[[int], None]] = None,
        destination_dir: Optional[Path] = None,
    ) -> Path:
        if not isinstance(info, UpdateInfo):
            raise UpdateError("No hay una actualización válida para descargar")
        url = _safe_url(info.download_url, allow_file=True)
        if destination_dir is None:
            base = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir())
            destination_dir = base / "Nikaido" / "updates"
        destination_dir.mkdir(parents=True, exist_ok=True)
        target = destination_dir / f"Nikaido_DualSense-{info.version}-Setup.exe"
        temp = target.with_suffix(target.suffix + ".part")
        digest = hashlib.sha256()
        received = 0
        request = urllib.request.Request(
            url,
            headers={"User-Agent": f"{APP_NAME.replace(' ', '-')}/{self.current_version}"},
        )
        try:
            with self._opener(request, timeout=DEFAULT_TIMEOUT) as response, open(temp, "wb") as stream:
                final_url = getattr(response, "geturl", lambda: url)()
                _safe_url(str(final_url or url), allow_file=True)
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > info.size_bytes or received > MAX_INSTALLER_BYTES:
                        raise UpdateError("La descarga excedió el tamaño anunciado")
                    stream.write(chunk)
                    digest.update(chunk)
                    if progress:
                        progress(max(0, min(100, int(received * 100 / info.size_bytes))))
                stream.flush()
                os.fsync(stream.fileno())
            if received != info.size_bytes:
                raise UpdateError("La descarga quedó incompleta")
            if digest.hexdigest().lower() != info.sha256.lower():
                raise UpdateError("La verificación SHA-256 del instalador falló")
            os.replace(temp, target)
        except Exception:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        with self._lock:
            self._downloaded_path = str(target)
        if progress:
            progress(100)
        return target

    def download_async(
        self,
        info: UpdateInfo,
        callback: Callable[[Optional[Path], str], None],
        *,
        progress: Optional[Callable[[int], None]] = None,
    ) -> threading.Thread:
        def worker() -> None:
            try:
                path = self.download(info, progress=progress)
                callback(path, "")
            except Exception as exc:
                callback(None, str(exc)[:300])

        thread = threading.Thread(target=worker, name="NikaidoUpdateDownload", daemon=True)
        thread.start()
        return thread

    def launch_installer(self, path: os.PathLike[str] | str, info: Optional[UpdateInfo] = None) -> bool:
        installer = Path(path)
        if os.name != "nt":
            raise UpdateError("El instalador solo puede ejecutarse en Windows")
        if not installer.is_file() or installer.suffix.lower() != ".exe":
            raise UpdateError("El instalador descargado ya no existe")
        args = list(info.silent_args if info and info.silent_args else ())
        if not args:
            args = ["/SP-", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"]
        subprocess.Popen([str(installer), *args], close_fds=True)
        return True

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            result = self._last_result.as_dict()
            return {
                "distribution": self.distribution,
                "manifest_configured": bool(self.manifest_url()),
                "channel": self.channel(),
                "last_check_at": self._last_check_at,
                "last_result": result,
                "downloaded_path": self._downloaded_path,
            }
