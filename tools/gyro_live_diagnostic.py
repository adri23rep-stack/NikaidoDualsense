#!/usr/bin/env python3
"""Diagnostico en vivo de la IMU del DualSense.

Ejecutar desde la raiz:
    python tools/gyro_live_diagnostic.py

No crea un control virtual ni modifica perfiles. Ctrl+C cierra limpiamente.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.connection_manager import ConnectionManager


def main():
    manager = ConnectionManager()
    last_print = 0.0

    def show(state):
        nonlocal last_print
        now = time.monotonic()
        if now - last_print < 1 / 30:
            return
        last_print = now
        print(
            f"\rGYRO  P {state.gyro_pitch:7d}  Y {state.gyro_yaw:7d}  R {state.gyro_roll:7d} | "
            f"ACCEL X {state.accel_x:7d}  Y {state.accel_y:7d}  Z {state.accel_z:7d} | "
            f"Touch {'ON ' if state.touchpad_active else 'OFF'} {state.touchpad_x:4d},{state.touchpad_y:3d}  ",
            end="", flush=True,
        )

    manager.on_connect(lambda kind: print(f"\nDualSense conectado por {kind.value}. Mueve el control..."))
    manager.on_disconnect(lambda: print("\nDualSense desconectado; buscando de nuevo..."))
    manager.on_state_update(show)
    manager.start()
    print("Buscando DualSense. Ctrl+C para salir.")
    try:
        while True:
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nCerrando diagnostico...")
    finally:
        manager.stop()


if __name__ == "__main__":
    main()
