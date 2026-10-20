"""Perfiles automáticos 2.0.

Selecciona perfiles por la ventana en primer plano y conserva compatibilidad
con el mapa histórico ``exe -> perfil``. Las reglas avanzadas permiten
prioridad, ruta, título de ventana, retrasos y restauración del perfil manual.
"""

from __future__ import annotations

import ctypes
import logging
import os
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    psutil = None
    PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)

MAX_GAME_PROFILE_RULES = 256
MAX_LEGACY_GAME_MAPPINGS = 512
MAX_RULE_PATH_LENGTH = 1024


def _clean_executable(value: Any) -> str:
    text = str(value or "").strip().strip('"')[:MAX_RULE_PATH_LENGTH]
    return Path(text).name.lower()[:260] if text else ""


def _clean_path(value: Any) -> str:
    text = str(value or "").strip().strip('"')
    if not text or len(text) > MAX_RULE_PATH_LENGTH:
        return ""
    try:
        return os.path.normcase(os.path.abspath(os.path.expandvars(text)))
    except (OSError, ValueError):
        return os.path.normcase(text)


def sanitize_rule(raw: Any, *, index: int = 0, legacy: bool = False) -> Dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    executable = _clean_executable(source.get("executable") or source.get("exe"))
    profile_id = str(source.get("profile_id") or source.get("profile") or "").strip()[:120]
    try:
        priority = max(-9999, min(9999, int(source.get("priority", 0))))
    except (TypeError, ValueError, OverflowError):
        priority = 0
    try:
        enter_delay_ms = max(0, min(10000, int(source.get("enter_delay_ms", 250))))
    except (TypeError, ValueError, OverflowError):
        enter_delay_ms = 250
    try:
        exit_delay_ms = max(0, min(10000, int(source.get("exit_delay_ms", 500))))
    except (TypeError, ValueError, OverflowError):
        exit_delay_ms = 500
    return {
        "id": str(source.get("id") or f"rule_{index}_{uuid.uuid4().hex[:8]}")[:120],
        "name": str(source.get("name") or executable or f"Regla {index + 1}").strip()[:80],
        "enabled": bool(source.get("enabled", True)),
        "executable": executable,
        "path": _clean_path(source.get("path")),
        "window_title": str(source.get("window_title") or "").strip().lower()[:160],
        "profile_id": profile_id,
        "priority": priority,
        "foreground_only": bool(source.get("foreground_only", not legacy)),
        "enter_delay_ms": enter_delay_ms,
        "exit_delay_ms": exit_delay_ms,
        "legacy": bool(source.get("legacy", legacy)),
    }


class GameProfileWatcher:
    """Aplica el perfil de la mejor regla y restaura el anterior al salir."""

    POLL_INTERVAL = 0.75
    HISTORY_LIMIT = 100

    def __init__(self, trigger_engine=None, foreground_provider=None):
        self.trigger_engine = trigger_engine
        self._foreground_provider = foreground_provider
        self._mapping: Dict[str, str] = {}
        self._rules: List[Dict[str, Any]] = []
        self._enabled = True
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()
        self._stop_event = threading.Event()

        self._current_game: Optional[str] = None
        self._current_profile: Optional[str] = None
        self._current_rule_id: Optional[str] = None
        self._base_profile: Optional[str] = None
        self._applying_profile: Optional[str] = None
        self._manual_override_key: Optional[tuple] = None
        self._candidate_key: Optional[tuple] = None
        self._candidate_since = 0.0
        self._last_foreground: Dict[str, Any] = {}
        self._history: deque[Dict[str, Any]] = deque(maxlen=self.HISTORY_LIMIT)
        self._on_game_change: List[Callable[[Optional[str], Optional[str]], None]] = []
        self._on_decision: List[Callable[[Dict[str, Any]], None]] = []

    # ------------------------------------------------------------------
    # Configuración

    def set_mapping(self, mapping: Dict[str, str]) -> None:
        cleaned: Dict[str, str] = {}
        for key, value in (mapping or {}).items():
            executable = _clean_executable(key)
            profile_id = str(value).strip()[:120]
            if executable and profile_id:
                cleaned[executable] = profile_id
            if len(cleaned) >= MAX_LEGACY_GAME_MAPPINGS:
                break
        with self._lock:
            self._mapping = cleaned
            # El mapa antiguo sigue funcionando como reglas de respaldo. No
            # exige foreground para conservar el comportamiento de 2.4.
            advanced = [rule for rule in self._rules if not rule.get("legacy")]
            legacy_rules = [
                sanitize_rule(
                    {
                        "id": f"legacy:{exe}",
                        "name": exe,
                        "executable": exe,
                        "profile_id": profile,
                        "priority": -100,
                        "foreground_only": False,
                        "enter_delay_ms": 0,
                        "exit_delay_ms": 0,
                    },
                    index=index,
                    legacy=True,
                )
                for index, (exe, profile) in enumerate(cleaned.items())
            ]
            self._rules = advanced + legacy_rules
            self._candidate_key = None

    def get_mapping(self) -> Dict[str, str]:
        with self._lock:
            return dict(self._mapping)

    def set_rules(self, rules: Iterable[Dict[str, Any]]) -> None:
        cleaned = []
        for index, raw in enumerate(rules or []):
            if len(cleaned) >= MAX_GAME_PROFILE_RULES:
                break
            rule = sanitize_rule(raw, index=index)
            if rule["executable"] and rule["profile_id"]:
                cleaned.append(rule)
        with self._lock:
            legacy = [rule for rule in self._rules if rule.get("legacy")]
            self._rules = cleaned + legacy
            self._candidate_key = None

    def get_rules(self, *, include_legacy: bool = False) -> List[Dict[str, Any]]:
        with self._lock:
            rules = [dict(rule) for rule in self._rules]
        return rules if include_legacy else [rule for rule in rules if not rule.get("legacy")]

    def add_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        cleaned = sanitize_rule(rule, index=len(self._rules))
        if not cleaned["executable"] or not cleaned["profile_id"]:
            raise ValueError("La regla necesita ejecutable y perfil")
        with self._lock:
            self._rules = [item for item in self._rules if item.get("id") != cleaned["id"]]
            self._rules.append(cleaned)
        return dict(cleaned)

    def remove_rule(self, rule_id: str) -> None:
        with self._lock:
            self._rules = [rule for rule in self._rules if rule.get("id") != str(rule_id)]

    def add_mapping(self, exe_name: str, profile_id: str) -> None:
        mapping = self.get_mapping()
        mapping[_clean_executable(exe_name)] = str(profile_id)
        self.set_mapping(mapping)

    def remove_mapping(self, exe_name: str) -> None:
        mapping = self.get_mapping()
        mapping.pop(_clean_executable(exe_name), None)
        self.set_mapping(mapping)

    def set_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        with self._lock:
            changed = enabled != self._enabled
            self._enabled = enabled
            self._candidate_key = None
        if changed and not enabled:
            self._publish_change(None, None, reason="automation_disabled", restore=True)

    def is_enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def is_available(self) -> bool:
        return PSUTIL_AVAILABLE

    def on_game_change(self, callback: Callable[[Optional[str], Optional[str]], None]) -> None:
        if not callable(callback):
            raise TypeError("El callback debe ser invocable")
        with self._lock:
            if callback not in self._on_game_change:
                self._on_game_change.append(callback)

    def on_decision(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        if not callable(callback):
            raise TypeError("El callback debe ser invocable")
        with self._lock:
            if callback not in self._on_decision:
                self._on_decision.append(callback)

    def observe_profile_change(self, profile_id: str) -> None:
        """Registra cambios manuales sin confundirlos con una aplicación automática."""
        profile_id = str(profile_id or "").strip()
        if not profile_id:
            return
        with self._lock:
            if profile_id == self._applying_profile:
                return
            self._base_profile = profile_id
            if self._current_rule_id:
                self._manual_override_key = (
                    self._current_rule_id,
                    self._current_game,
                    self._current_profile,
                )
                self._record_locked(
                    "manual_override", self._current_game, profile_id, self._current_rule_id
                )

    def get_current_game(self) -> Optional[str]:
        with self._lock:
            return self._current_game

    # ------------------------------------------------------------------
    # Ciclo de vida

    def start(self) -> None:
        if not PSUTIL_AVAILABLE:
            logger.warning("psutil no está instalado: perfiles automáticos desactivados")
            return
        with self._lifecycle_lock:
            with self._lock:
                if self._running or (self._thread and self._thread.is_alive()):
                    return
                self._running = True
                self._stop_event.clear()
                self._thread = threading.Thread(
                    target=self._watch_loop, name="GameProfileWatcher", daemon=True
                )
                thread = self._thread
            thread.start()
        logger.info("GameProfileWatcher 2.0 iniciado")

    def stop(self) -> None:
        with self._lifecycle_lock:
            with self._lock:
                self._running = False
                self._stop_event.set()
                thread = self._thread
            if thread and thread is not threading.current_thread() and thread.is_alive():
                thread.join(timeout=max(0.5, self.POLL_INTERVAL + 0.5))
            with self._lock:
                if self._thread is thread and (thread is None or not thread.is_alive()):
                    self._thread = None
        logger.info("GameProfileWatcher detenido")

    def _watch_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                if self.is_enabled():
                    self._poll_stable()
            except Exception:
                logger.exception("Fallo revisando perfiles automáticos")
            self._stop_event.wait(self.POLL_INTERVAL)

    # ------------------------------------------------------------------
    # Detección

    def _foreground_window(self) -> Dict[str, Any]:
        provider = self._foreground_provider
        if callable(provider):
            try:
                value = provider()
                return dict(value) if isinstance(value, dict) else {}
            except Exception as exc:
                logger.debug("Proveedor de ventana activa falló: %s", exc)
                return {}
        if os.name != "nt" or psutil is None:
            return {}
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return {}
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            length = user32.GetWindowTextLengthW(hwnd)
            buffer = ctypes.create_unicode_buffer(max(1, length + 1))
            user32.GetWindowTextW(hwnd, buffer, len(buffer))
            process = psutil.Process(int(pid.value))
            path = ""
            try:
                path = process.exe()
            except Exception:
                pass
            return {
                "pid": int(pid.value),
                "executable": _clean_executable(process.name()),
                "path": _clean_path(path),
                "title": str(buffer.value or ""),
            }
        except Exception as exc:
            logger.debug("No se pudo leer la ventana activa: %s", exc)
            return {}

    def _running_processes(self) -> List[Dict[str, Any]]:
        if psutil is None:
            return []
        processes = []
        try:
            for process in psutil.process_iter(["pid", "name", "exe"]):
                info = getattr(process, "info", {}) or {}
                name = _clean_executable(info.get("name"))
                if not name:
                    continue
                processes.append(
                    {
                        "pid": int(info.get("pid") or 0),
                        "executable": name,
                        "path": _clean_path(info.get("exe")),
                        "title": "",
                    }
                )
        except Exception as exc:
            logger.debug("Error iterando procesos: %s", exc)
        return processes

    @staticmethod
    def _rule_matches(rule: Dict[str, Any], process: Dict[str, Any], *, foreground: bool) -> bool:
        if not rule.get("enabled") or not rule.get("profile_id"):
            return False
        if rule.get("foreground_only") and not foreground:
            return False
        if rule.get("executable") != process.get("executable"):
            return False
        wanted_path = rule.get("path") or ""
        if wanted_path and _clean_path(process.get("path")) != wanted_path:
            return False
        title = str(process.get("title") or "").lower()
        wanted_title = rule.get("window_title") or ""
        if wanted_title and wanted_title not in title:
            return False
        return True

    def _select_match(self) -> tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        with self._lock:
            rules = [dict(rule) for rule in self._rules if rule.get("enabled")]
        foreground = self._foreground_window()
        self._last_foreground = dict(foreground)
        candidates = []
        if foreground:
            for rule in rules:
                if self._rule_matches(rule, foreground, foreground=True):
                    candidates.append((1, rule, foreground))
        running = self._running_processes()
        for process in running:
            # El proceso activo ya se agregó con mayor rango.
            is_foreground = bool(foreground and process.get("pid") == foreground.get("pid"))
            if is_foreground:
                continue
            for rule in rules:
                if self._rule_matches(rule, process, foreground=False):
                    candidates.append((0, rule, process))
        if not candidates:
            return None, foreground
        candidates.sort(
            key=lambda item: (
                item[0],
                int(item[1].get("priority", 0)),
                bool(item[1].get("path")),
                bool(item[1].get("window_title")),
                -rules.index(item[1]),
            ),
            reverse=True,
        )
        _foreground_rank, rule, process = candidates[0]
        return {"rule": rule, "process": process}, foreground

    def _check_processes(self) -> None:
        """Chequeo inmediato conservado para pruebas y herramientas de soporte."""
        match, _foreground = self._select_match()
        if match:
            rule, process = match["rule"], match["process"]
            self._publish_change(
                process.get("executable"),
                rule.get("profile_id"),
                rule=rule,
                reason="immediate_match",
            )
        else:
            self._publish_change(None, None, reason="immediate_no_match", restore=True)

    def _poll_stable(self) -> None:
        match, _foreground = self._select_match()
        if match:
            rule, process = match["rule"], match["process"]
            desired = (rule.get("id"), process.get("executable"), rule.get("profile_id"))
            delay_ms = int(rule.get("enter_delay_ms", 0))
        else:
            desired = (None, None, None)
            with self._lock:
                current_rule = next(
                    (rule for rule in self._rules if rule.get("id") == self._current_rule_id),
                    None,
                )
            delay_ms = int((current_rule or {}).get("exit_delay_ms", 0))

        now = time.monotonic()
        with self._lock:
            if desired != self._candidate_key:
                self._candidate_key = desired
                self._candidate_since = now
                return
            stable_ms = (now - self._candidate_since) * 1000.0
            manual_override = self._manual_override_key
        if stable_ms < delay_ms:
            return
        if manual_override and desired == manual_override:
            return
        if match:
            self._publish_change(desired[1], desired[2], rule=match["rule"], reason="stable_match")
        else:
            self._publish_change(None, None, reason="stable_no_match", restore=True)

    # ------------------------------------------------------------------
    # Aplicación y diagnóstico

    def _engine_current_profile(self) -> Optional[str]:
        getter = getattr(self.trigger_engine, "get_current_profile", None)
        if not callable(getter):
            return None
        try:
            value = getter()
            return str(value) if value else None
        except Exception:
            return None

    def _apply_profile(self, profile_id: str) -> bool:
        engine = self.trigger_engine
        if not engine or not profile_id:
            return False
        with self._lock:
            self._applying_profile = profile_id
        try:
            return bool(engine.apply_profile(profile_id))
        finally:
            with self._lock:
                self._applying_profile = None

    def _publish_change(
        self,
        exe_name: Optional[str],
        profile_id: Optional[str],
        *,
        rule: Optional[Dict[str, Any]] = None,
        reason: str = "change",
        restore: bool = False,
    ) -> None:
        rule_id = str((rule or {}).get("id") or "") or None
        with self._lock:
            same = (exe_name, profile_id, rule_id) == (
                self._current_game,
                self._current_profile,
                self._current_rule_id,
            )
            if same and not restore:
                return
            previous_rule = self._current_rule_id
            if profile_id and not previous_rule and not self._base_profile:
                self._base_profile = self._engine_current_profile()
            restore_profile = self._base_profile if restore and previous_rule else None
            if restore:
                self._current_game = None
                self._current_profile = None
                self._current_rule_id = None
                self._manual_override_key = None
            else:
                self._current_game = exe_name
                self._current_profile = profile_id
                self._current_rule_id = rule_id
                self._manual_override_key = None
            callbacks = tuple(self._on_game_change)
            decision_callbacks = tuple(self._on_decision)

        applied_profile = None
        if profile_id:
            if self._apply_profile(profile_id):
                applied_profile = profile_id
                logger.info("Perfil automático: %s -> %s", exe_name, profile_id)
        elif restore_profile:
            if self._apply_profile(restore_profile):
                applied_profile = restore_profile
                logger.info("Perfil automático finalizado; restaurado %s", restore_profile)

        with self._lock:
            if restore:
                self._base_profile = applied_profile or self._base_profile
            self._record_locked(reason, exe_name, applied_profile or profile_id, rule_id)
            event = dict(self._history[-1])

        failed = []
        for callback in callbacks:
            try:
                callback(exe_name, profile_id)
            except Exception:
                logger.exception("Callback de perfil automático desactivado tras fallar")
                failed.append(callback)
        failed_decisions = []
        for callback in decision_callbacks:
            try:
                callback(dict(event))
            except Exception:
                logger.exception("Callback de decisión automática desactivado tras fallar")
                failed_decisions.append(callback)
        if failed or failed_decisions:
            with self._lock:
                self._on_game_change[:] = [cb for cb in self._on_game_change if cb not in failed]
                self._on_decision[:] = [
                    cb for cb in self._on_decision if cb not in failed_decisions
                ]

    def _record_locked(
        self,
        reason: str,
        exe_name: Optional[str],
        profile_id: Optional[str],
        rule_id: Optional[str],
    ) -> None:
        self._history.append(
            {
                "timestamp": time.time(),
                "reason": str(reason),
                "executable": exe_name,
                "profile_id": profile_id,
                "rule_id": rule_id,
                "foreground": dict(self._last_foreground),
            }
        )

    def get_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._history]

    def get_diagnostics_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "available": PSUTIL_AVAILABLE,
                "enabled": self._enabled,
                "running": bool(self._thread and self._thread.is_alive()),
                "rules": len([rule for rule in self._rules if not rule.get("legacy")]),
                "legacy_mappings": len(self._mapping),
                "current_game": self._current_game,
                "current_profile": self._current_profile,
                "current_rule_id": self._current_rule_id,
                "base_profile": self._base_profile,
                "foreground": dict(self._last_foreground),
                "manual_override": bool(self._manual_override_key),
                "history": [dict(item) for item in list(self._history)[-10:]],
            }
