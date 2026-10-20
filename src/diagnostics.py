"""Centro de diagnóstico de Nikaido.

El motor reúne métricas ya calculadas por la ruta HID/ViGEm sin meter trabajo
pesado en el hilo de baja latencia. También puede capturar una sesión corta y
crear un ZIP sanitizado para reportar fallos sin incluir nombres de usuario,
rutas personales ni argumentos de procesos.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import threading
import time
import zipfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from nikaido_version import APP_NAME, APP_VERSION
from .security_utils import redact_private_text

logger = logging.getLogger(__name__)

try:
    import psutil
except ImportError:  # pragma: no cover - dependencia normal del proyecto
    psutil = None


CONFLICT_PROCESSES = {
    "ds4windows.exe": "DS4Windows",
    "dualsensex.exe": "DualSenseX",
    "dualsensex.app.exe": "DualSenseX",
    "dualsenseat.exe": "DualSenseAT",
    "rewasd.exe": "reWASD",
    "inputmapper.exe": "InputMapper",
    "scptoolkit.exe": "SCPToolkit",
    "steam.exe": "Steam (revisa si Steam Input está activo)",
}


class DiagnosticEngine:
    """Agrega telemetría y genera reportes seguros para soporte."""

    # El reporte solo adjunta los últimos diez segundos. Mantener más muestras
    # anidadas no añadía información al ZIP y sí retenía varios MB todo el día.
    MAX_HISTORY_SECONDS = 10
    OBSERVER_HZ = 60

    def __init__(
        self,
        connection_manager=None,
        emulator=None,
        gyro_engine=None,
        advanced_mapper=None,
        macro_engine=None,
        profile_manager=None,
        trigger_engine=None,
        virtual_feedback_bridge=None,
        game_profile_watcher=None,
        hidhide_manager=None,
        update_manager=None,
    ) -> None:
        self.connection_manager = connection_manager
        self.emulator = emulator or getattr(connection_manager, "emulator", None)
        self.gyro_engine = gyro_engine
        self.advanced_mapper = advanced_mapper
        self.macro_engine = macro_engine
        self.profile_manager = profile_manager
        self.trigger_engine = trigger_engine
        self.virtual_feedback_bridge = virtual_feedback_bridge
        self.game_profile_watcher = game_profile_watcher
        self.hidhide_manager = hidhide_manager
        self.update_manager = update_manager

        self._lock = threading.RLock()
        self._history: deque[Dict[str, Any]] = deque(
            maxlen=self.MAX_HISTORY_SECONDS * self.OBSERVER_HZ
        )
        self._last_history_sample_at = 0.0
        self._capture: List[Dict[str, Any]] = []
        self._capture_started = 0.0
        self._capture_duration = 0.0
        self._capture_active = False
        self._last_conflict_scan = 0.0
        self._conflict_scan_running = False
        self._conflicts: List[str] = []
        self._events: deque[Dict[str, Any]] = deque(maxlen=200)

        if connection_manager and hasattr(connection_manager, "on_state_update"):
            connection_manager.on_state_update(self._on_state)
        if connection_manager and hasattr(connection_manager, "on_connect"):
            connection_manager.on_connect(
                lambda connection: self.add_event(
                    "connect", f"DualSense conectado por {getattr(connection, 'value', connection)}"
                )
            )
        if connection_manager and hasattr(connection_manager, "on_disconnect"):
            connection_manager.on_disconnect(
                lambda: self.add_event("disconnect", "DualSense desconectado")
            )
        if connection_manager and hasattr(connection_manager, "on_error"):
            connection_manager.on_error(
                lambda message: self.add_event("error", str(message), severity="error")
            )
        if trigger_engine and hasattr(trigger_engine, "on_profile_change"):
            trigger_engine.on_profile_change(
                lambda profile_id: self.add_event(
                    "profile", f"Perfil activo: {profile_id}"
                )
            )

    # ------------------------------------------------------------------
    # Captura

    def start_capture(self, duration: float = 10.0) -> float:
        duration = max(3.0, min(30.0, float(duration)))
        with self._lock:
            self._capture = []
            self._capture_started = time.monotonic()
            self._capture_duration = duration
            self._capture_active = True
        self.add_event("capture", f"Captura iniciada ({duration:.0f} s)")
        return duration

    def stop_capture(self) -> List[Dict[str, Any]]:
        with self._lock:
            was_active = self._capture_active
            self._capture_active = False
            result = list(self._capture)
        if was_active:
            self.add_event("capture", f"Captura detenida ({len(result)} muestras)")
        return result

    def clear_capture(self) -> None:
        with self._lock:
            self._capture.clear()
            self._capture_active = False
            self._capture_started = 0.0
            self._capture_duration = 0.0

    def capture_status(self) -> Dict[str, Any]:
        with self._lock:
            elapsed = max(0.0, time.monotonic() - self._capture_started) if self._capture_started else 0.0
            if self._capture_active and elapsed >= self._capture_duration:
                self._capture_active = False
            duration = self._capture_duration
            return {
                "active": self._capture_active,
                "elapsed": min(elapsed, duration) if duration else 0.0,
                "duration": duration,
                "progress": min(1.0, elapsed / duration) if duration else 0.0,
                "samples": len(self._capture),
            }

    def get_capture(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._capture)

    def _on_state(self, state: Any) -> None:
        now = time.monotonic()
        interval = 1.0 / self.OBSERVER_HZ
        with self._lock:
            capture_active = self._capture_active
            history_due = (
                self._last_history_sample_at <= 0.0
                or now - self._last_history_sample_at >= interval
            )
            if history_due:
                self._last_history_sample_at = now
        # La entrada HID puede llegar a 250-1000 Hz. Construir varios diccionarios
        # anidados en cada tick llenaba la RAM aunque el diagnóstico promete 60 Hz.
        if not history_due and not capture_active:
            return
        sample = self._state_sample(state)
        with self._lock:
            if history_due:
                self._history.append(sample)
            if self._capture_active:
                elapsed = now - self._capture_started
                if elapsed <= self._capture_duration:
                    self._capture.append(sample)
                else:
                    self._capture_active = False

    def _state_sample(self, state: Any) -> Dict[str, Any]:
        buttons = getattr(state, "buttons", {}) or {}
        pressed = sorted(str(key) for key, value in buttons.items() if value)
        physical = {
            "sequence": int(getattr(state, "sequence", -1)),
            "source": str(getattr(state, "source", "unknown")),
            "sticks": {
                "lx": int(getattr(state, "left_stick_x", 128)),
                "ly": int(getattr(state, "left_stick_y", 128)),
                "rx": int(getattr(state, "right_stick_x", 128)),
                "ry": int(getattr(state, "right_stick_y", 128)),
            },
            "triggers": {
                "l2": int(getattr(state, "left_trigger", 0)),
                "r2": int(getattr(state, "right_trigger", 0)),
            },
            "buttons": pressed,
            "gyro": [
                int(getattr(state, "gyro_pitch", 0)),
                int(getattr(state, "gyro_yaw", 0)),
                int(getattr(state, "gyro_roll", 0)),
            ],
            "accel": [
                int(getattr(state, "accel_x", 0)),
                int(getattr(state, "accel_y", 0)),
                int(getattr(state, "accel_z", 0)),
            ],
        }
        virtual = self._safe_snapshot(self.emulator, "get_output_state_snapshot")
        timing = self._safe_snapshot(self.connection_manager, "get_last_pipeline_sample")
        captured_ns = int(getattr(state, "monotonic_ns", 0) or 0)
        virtual_ns = int(virtual.get("updated_ns", 0) or 0)
        if (
            captured_ns > 0
            and virtual_ns >= captured_ns
            and int(virtual.get("sequence", -2)) == physical["sequence"]
        ):
            timing["physical_snapshot_to_vigem_ms"] = round(
                (virtual_ns - captured_ns) / 1_000_000.0, 4
            )
        else:
            timing["physical_snapshot_to_vigem_ms"] = None

        # Campos planos conservados para que herramientas de soporte 2.1.0
        # puedan leer capturas nuevas sin romperse.
        return {
            "t": round(time.monotonic(), 6),
            "sequence": physical["sequence"],
            "source": physical["source"],
            "sticks": physical["sticks"],
            "triggers": physical["triggers"],
            "buttons": physical["buttons"],
            "gyro": physical["gyro"],
            "accel": physical["accel"],
            "physical": physical,
            "virtual": virtual,
            "timing": timing,
        }

    # ------------------------------------------------------------------
    # Estado y salud

    def add_event(self, category: str, message: str, *, severity: str = "info") -> None:
        with self._lock:
            self._events.append(
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "category": str(category),
                    "severity": str(severity),
                    "message": str(message)[:500],
                }
            )

    def scan_conflicts(self, *, force: bool = False) -> List[str]:
        """Devuelve la caché y actualiza procesos fuera del hilo de la UI.

        Enumerar procesos suele ser rápido, pero en equipos cargados o con un
        antivirus agresivo puede tardar lo suficiente para sentirse como un
        tirón. La pantalla usa una actualización asíncrona; al generar un
        reporte se permite ``force=True`` para obtener el estado inmediato.
        """
        now = time.monotonic()
        with self._lock:
            cached = list(self._conflicts)
            fresh = now - self._last_conflict_scan < 5.0
            running = self._conflict_scan_running
            if not force and (fresh or running):
                return cached
            if not force:
                self._conflict_scan_running = True

        if force:
            return self._scan_conflicts_now()

        threading.Thread(
            target=self._scan_conflicts_now,
            name="NikaidoConflictScan",
            daemon=True,
        ).start()
        return cached

    def _scan_conflicts_now(self) -> List[str]:
        found: set[str] = set()
        if psutil is not None:
            try:
                for process in psutil.process_iter(["name"]):
                    name = str(process.info.get("name") or "").lower()
                    friendly = CONFLICT_PROCESSES.get(name)
                    if friendly:
                        found.add(friendly)
            except Exception as exc:
                logger.debug("No se pudo revisar procesos en conflicto: %s", exc)
        with self._lock:
            self._conflicts = sorted(found)
            self._last_conflict_scan = time.monotonic()
            self._conflict_scan_running = False
            return list(self._conflicts)

    def snapshot(self) -> Dict[str, Any]:
        connection = self._safe_snapshot(self.connection_manager, "get_diagnostics_snapshot")
        emulator = self._safe_snapshot(self.emulator, "get_diagnostics_snapshot")
        gyro = self._gyro_snapshot()
        mapper = self._safe_snapshot(self.advanced_mapper, "get_diagnostics_snapshot")
        virtual_feedback = self._safe_snapshot(
            self.virtual_feedback_bridge, "get_diagnostics_snapshot"
        )
        automatic_profiles = self._safe_snapshot(
            self.game_profile_watcher, "get_diagnostics_snapshot"
        )
        hidhide = self._hidhide_snapshot(emulator)
        updates = self._safe_snapshot(self.update_manager, "snapshot")
        capture = self.capture_status()
        conflicts = self.scan_conflicts()
        with self._lock:
            events = list(self._events)[-20:]

        health, issues, advisories = self._health(
            connection, emulator, gyro, conflicts, virtual_feedback, hidhide
        )
        return {
            "health": health,
            "issues": issues,
            "advisories": advisories,
            "connection": connection,
            "emulator": emulator,
            "gyro": gyro,
            "mapper": mapper,
            "virtual_feedback": virtual_feedback,
            "automatic_profiles": automatic_profiles,
            "hidhide": hidhide,
            "updates": updates,
            "capture": capture,
            "conflicts": conflicts,
            "events": events,
            "profile": self._active_profile(),
            "process": self._process_snapshot(),
        }

    def _hidhide_snapshot(self, emulator: Mapping[str, Any]) -> Dict[str, Any]:
        manager = self.hidhide_manager
        if manager is None:
            return {}
        scanner = getattr(manager, "scan", None)
        if not callable(scanner):
            return self._safe_snapshot(manager, "get_diagnostics_snapshot")
        try:
            return dict(scanner(
                force=False,
                emulator_active=bool(emulator.get("active", False)),
            ))
        except Exception as exc:
            logger.debug("Revisión de HidHide falló: %s", exc)
            return self._safe_snapshot(manager, "get_diagnostics_snapshot")

    @staticmethod
    def _safe_snapshot(target: Any, method_name: str) -> Dict[str, Any]:
        if target is None:
            return {}
        method = getattr(target, method_name, None)
        if not callable(method):
            return {}
        try:
            value = method()
            return dict(value) if isinstance(value, Mapping) else {}
        except Exception as exc:
            logger.debug("Snapshot de diagnóstico falló: %s", exc)
            return {}

    def _gyro_snapshot(self) -> Dict[str, Any]:
        if not self.gyro_engine:
            return {}
        try:
            telemetry = self.gyro_engine.get_telemetry()
            config = self.gyro_engine.get_config()
            return {
                "mode": telemetry.mode,
                "active": bool(telemetry.active),
                "sample_hz": round(float(telemetry.sample_hz), 2),
                "processed_sample_hz": round(float(telemetry.sample_hz), 2),
                "rate_basis": "unique_source_sequences",
                "calibrated": bool(telemetry.calibrated),
                "output": [round(float(telemetry.output_x), 3), round(float(telemetry.output_y), 3)],
                "flick_active": bool(getattr(telemetry, "flick_active", False)),
                "enabled": bool(config.enabled),
                "flick_enabled": bool(getattr(config, "flick_stick_enabled", False)),
            }
        except Exception:
            return {}

    def _active_profile(self) -> str:
        try:
            return str(self.trigger_engine.get_current_profile() or "")
        except Exception:
            return ""

    @staticmethod
    def _process_snapshot() -> Dict[str, Any]:
        result = {"ram_mb": 0.0, "threads": threading.active_count(), "cpu_percent": 0.0}
        if psutil is None:
            return result
        try:
            process = psutil.Process(os.getpid())
            result["ram_mb"] = round(process.memory_info().rss / (1024 * 1024), 1)
            result["threads"] = int(process.num_threads())
            result["cpu_percent"] = round(float(process.cpu_percent(None)), 1)
        except Exception:
            pass
        return result

    @staticmethod
    def _health(
        connection: Mapping[str, Any],
        emulator: Mapping[str, Any],
        gyro: Mapping[str, Any],
        conflicts: Iterable[str],
        virtual_feedback: Optional[Mapping[str, Any]] = None,
        hidhide: Optional[Mapping[str, Any]] = None,
    ) -> tuple[str, List[str], List[str]]:
        issues: List[str] = []
        advisories: List[str] = []
        connected = bool(connection.get("connected", False))
        if not connected:
            issues.append("No hay un DualSense conectado")

        # ``device_report_hz`` se estima con el avance real del contador Sony.
        # ``fresh_snapshot_hz`` solo dice cuántas copias nuevas alcanzó a ver
        # Nikaido y nunca debe tratarse como pérdida del bus.
        device_hz = float(connection.get("device_report_hz", 0.0) or 0.0)
        processing_hz = float(
            connection.get("processing_hz", connection.get("poll_hz", 0.0)) or 0.0
        )
        if connected and device_hz and device_hz < 40.0:
            issues.append(f"Frecuencia física HID baja ({device_hz:.0f} Hz)")
        if connected and processing_hz and processing_hz < 55.0:
            issues.append(f"Procesamiento de entrada bajo ({processing_hz:.0f} Hz)")

        read_failures = int(connection.get("read_failures", 0) or 0)
        if read_failures >= 3:
            issues.append(f"Hay {read_failures} fallos consecutivos de lectura")
        discontinuities = int(connection.get("sequence_discontinuities", 0) or 0)
        if discontinuities:
            advisories.append(
                f"El contador HID se reinició o saltó {discontinuities} vez/veces"
            )

        p95 = float(connection.get("pipeline_p95_ms", 0.0) or 0.0)
        if p95 > 8.0:
            issues.append(f"La ruta de entrada tiene picos de {p95:.1f} ms")
        if emulator.get("last_error"):
            issues.append("El control virtual reportó un error")
        feedback = virtual_feedback or {}
        if feedback.get("enabled") and feedback.get("last_error"):
            advisories.append("La vibración del juego no pudo llegar al DualSense físico")
        hide = hidhide or {}
        if hide.get("duplicate_risk"):
            advisories.append("La emulación está activa y HidHide no está listo; puede haber doble entrada")

        confirmed_conflicts = [
            name for name in conflicts if not str(name).startswith("Steam (")
        ]
        if confirmed_conflicts:
            issues.append("Hay programas que podrían duplicar la entrada")
        if any(str(name).startswith("Steam (") for name in conflicts):
            advisories.append("Steam está abierto; revisa Steam Input si notas doble entrada")

        # El passthrough DS4 cuenta con centrado temporal; no tener una
        # calibración permanente es una recomendación, no una falla.
        if gyro.get("enabled") and not gyro.get("calibrated"):
            advisories.append("El giroscopio usa centrado temporal; puedes guardar una calibración")

        if not issues:
            return "excellent", [], advisories
        if len(issues) <= 2 and not emulator.get("last_error"):
            return "warning", issues, advisories
        return "problem", issues, advisories

    # ------------------------------------------------------------------
    # Reporte

    def generate_report(self, destination: str) -> str:
        target = Path(destination)
        if target.suffix.lower() != ".zip":
            target = target.with_suffix(".zip")
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".tmp")

        self.scan_conflicts(force=True)
        snapshot = self.snapshot()
        capture = self.get_capture()
        if not capture:
            with self._lock:
                capture = list(self._history)[-10 * self.OBSERVER_HZ :]

        report = {
            "format": "Nikaido Diagnostic Report",
            "version": 2,
            "app": {"name": APP_NAME, "version": APP_VERSION},
            "metric_definitions": {
                "device_report_hz": "Frecuencia física estimada por avance del contador HID Sony",
                "processing_hz": "Ticks por segundo procesados por Nikaido",
                "fresh_snapshot_hz": "Copias nuevas observadas por Nikaido; no equivale a frecuencia física",
                "coalesced_reports": "Informes intermedios reemplazados por el estado más reciente; no son pérdidas",
                "pipeline_ms": "Tiempo interno desde comenzar la lectura hasta terminar ViGEm",
                "physical_snapshot_to_vigem_ms": "Tiempo desde crear la copia física hasta confirmar la escritura virtual",
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
            "system": {
                "os": platform.system(),
                "os_release": platform.release(),
                "python": platform.python_version(),
                "machine": platform.machine(),
            },
            "snapshot": snapshot,
            "capture_samples": len(capture),
        }
        # Los mensajes de error pueden venir de librerías externas e incluir
        # una ruta de Windows. Sanitizamos de forma recursiva justo antes de
        # escribir el paquete para que la garantía de privacidad no dependa de
        # qué módulo originó el texto.
        report = self._sanitize_value(report)
        capture = self._sanitize_value(capture)
        summary = self._summary_text(report)

        try:
            with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("report.json", json.dumps(report, ensure_ascii=False, indent=2))
                archive.writestr("capture.json", json.dumps(capture, ensure_ascii=False, separators=(",", ":")))
                archive.writestr("summary.txt", summary)
                archive.writestr(
                    "PRIVACY.txt",
                    "Este reporte no incluye nombre de usuario, rutas personales, argumentos de procesos, "
                    "contenido de macros ni archivos de perfiles.\n",
                )
            os.replace(temp, target)
        except Exception:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        self.add_event("report", "Reporte de diagnóstico generado")
        return str(target)

    @classmethod
    def _sanitize_value(cls, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(key): cls._sanitize_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._sanitize_value(item) for item in value]
        if isinstance(value, str):
            return redact_private_text(value)
        return value

    def generate_summary_text(self) -> str:
        """Crea un resumen copiable sin rutas personales ni contenido de perfiles."""
        self.scan_conflicts(force=True)
        report = {
            "snapshot": self._sanitize_value(self.snapshot()),
        }
        return redact_private_text(self._summary_text(report))

    @staticmethod
    def _summary_text(report: Mapping[str, Any]) -> str:
        snapshot = report.get("snapshot", {}) or {}
        connection = snapshot.get("connection", {}) or {}
        emulator = snapshot.get("emulator", {}) or {}
        gyro = snapshot.get("gyro", {}) or {}
        issues = snapshot.get("issues", []) or []
        advisories = snapshot.get("advisories", []) or []
        lines = [
            f"{APP_NAME} {APP_VERSION} — Reporte de diagnóstico",
            "=" * 58,
            f"Salud: {snapshot.get('health', 'unknown')}",
            f"Conexión: {connection.get('connection_type', 'none')}",
            f"HID físico estimado: {connection.get('device_report_hz', 0)} Hz",
            f"Procesamiento Nikaido: {connection.get('processing_hz', connection.get('poll_hz', 0))} Hz",
            f"Estados nuevos observados: {connection.get('fresh_snapshot_hz', connection.get('unique_hid_hz', 0))} Hz",
            f"Ruta promedio / p95: {connection.get('pipeline_avg_ms', 0)} / {connection.get('pipeline_p95_ms', 0)} ms",
            f"Botones promedio / p95: {connection.get('button_edge_avg_ms', 0)} / {connection.get('button_edge_p95_ms', 0)} ms",
            f"Lecturas fallidas: {connection.get('read_failures', 0)}",
            f"Informes intermedios omitidos: {connection.get('coalesced_reports', 0)} (esperado al conservar el estado más reciente)",
            f"Control virtual: {emulator.get('mode', 'none')} · {emulator.get('virtual_hz', 0)} Hz",
            f"Gyro procesado: {gyro.get('mode', 'disabled')} · {gyro.get('processed_sample_hz', gyro.get('sample_hz', 0))} Hz",
            "",
            "Problemas detectados:",
        ]
        if issues:
            lines.extend(f"- {issue}" for issue in issues)
        else:
            lines.append("- Ninguno")
        lines.append("")
        lines.append("Avisos informativos:")
        if advisories:
            lines.extend(f"- {item}" for item in advisories)
        else:
            lines.append("- Ninguno")
        return "\n".join(lines) + "\n"
