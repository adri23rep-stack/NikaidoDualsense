"""Auto-prueba corta para validar una copia actual de Nikaido.

No sustituye una sesión real con un DualSense. Comprueba configuración,
perfiles automáticos, feedback aislado y disponibilidad de HidHide/ViGEm.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nikaido_version import APP_VERSION  # noqa: E402
from src.game_profile_watcher import GameProfileWatcher  # noqa: E402
from src.hidhide_manager import HidHideManager  # noqa: E402
from src.mouse_to_gyro import MouseGyroSource  # noqa: E402
from src.profile_manager import ProfileManager  # noqa: E402
from src.virtual_feedback import VirtualFeedbackBridge  # noqa: E402


class _Trigger:
    def __init__(self):
        self.current = "desktop"
        self.applied = []

    def get_current_profile(self):
        return self.current

    def apply_profile(self, profile_id):
        self.current = str(profile_id)
        self.applied.append(self.current)
        return True


class _Emulator:
    def __init__(self):
        self.callbacks = []

    def on_feedback(self, callback):
        self.callbacks.append(callback)

    def remove_feedback_callback(self, callback):
        if callback in self.callbacks:
            self.callbacks.remove(callback)


class _Connection:
    def __init__(self):
        self.last = (0, 0)

    def set_rumble(self, left, right):
        self.last = (int(left), int(right))


def run() -> dict:
    result = {"version": APP_VERSION, "checks": {}, "ok": False}
    with tempfile.TemporaryDirectory(prefix="nikaido25-") as temp:
        manager = ProfileManager(temp)
        result["checks"]["config_defaults"] = bool(
            manager.get_setting("virtual_feedback", {}).get("enabled")
            and isinstance(manager.get_setting("game_profile_rules", []), list)
        )

    trigger = _Trigger()
    foreground = {"pid": 1, "executable": "selftest.exe", "path": "", "title": "Selftest"}
    watcher = GameProfileWatcher(trigger, foreground_provider=lambda: dict(foreground))
    watcher._running_processes = lambda: []
    watcher.set_rules([{"executable": "selftest.exe", "profile_id": "game", "priority": 10}])
    watcher._check_processes()
    foreground.clear()
    watcher._check_processes()
    result["checks"]["automatic_profiles"] = trigger.applied == ["game", "desktop"]

    emulator = _Emulator()
    connection = _Connection()
    bridge = VirtualFeedbackBridge(
        emulator, connection, {"smoothing_ms": 0, "idle_timeout_ms": 100}
    )
    bridge.start()
    emulator.callbacks[0]({"large_motor": 120, "small_motor": 40})
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline and connection.last != (120, 40):
        time.sleep(0.01)
    result["checks"]["virtual_feedback"] = connection.last == (120, 40)
    bridge.stop()
    result["checks"]["feedback_neutralized"] = connection.last == (0, 0)

    mouse = MouseGyroSource()
    mouse.feed_delta(9, -4)
    result["checks"]["mouse_capture_pipeline"] = mouse.consume_delta() == (9.0, -4.0)

    hide = HidHideManager().scan(force=True, emulator_active=False)
    result["hidhide"] = {
        key: hide.get(key) for key in ("supported", "installed", "version", "ready", "issues")
    }
    result["ok"] = all(result["checks"].values())
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-prueba de Nikaido")
    parser.add_argument("--output", default="", help="Guardar resultado JSON")
    args = parser.parse_args()
    result = run()
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    print(payload)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
