"""Diagnóstico de solo lectura para Audio de Windows y HidHide."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    report: dict[str, object] = {
        "platform": sys.platform,
        "os_name": os.name,
        "python": str(Path(sys.executable).resolve()),
        "audio": {},
        "hidhide": {},
    }

    try:
        from src.audio_manager import PycawCaptureBackend

        backend = PycawCaptureBackend()
        backend.initialize()
        try:
            devices = backend.list_capture_devices(force=True)
            states = []
            for device in devices:
                try:
                    state = backend.get_state(device.id)
                    states.append(
                        {
                            "id": state.device_id,
                            "name": state.name,
                            "muted": state.muted,
                            "volume": state.volume,
                            "default": device.is_default,
                            "dualsense": device.is_dualsense,
                        }
                    )
                except Exception as exc:
                    states.append(
                        {
                            "id": device.id,
                            "name": device.name,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
            report["audio"] = {"ok": True, "devices": states}
        finally:
            backend.shutdown()
    except Exception as exc:
        report["audio"] = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    try:
        from src.hidhide_manager import HidHideManager

        manager = HidHideManager()
        report["hidhide"] = manager.scan(force=True, emulator_active=False)
    except Exception as exc:
        report["hidhide"] = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    destination = root / "diagnostico_audio_hidhide.json"
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"\nReporte guardado en: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
