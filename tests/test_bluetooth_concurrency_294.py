"""Regresiones de concurrencia para la reparación Bluetooth segura."""

from __future__ import annotations

import threading

from src.bluetooth_utils import BluetoothManager


def test_only_one_full_bluetooth_reset_can_run_at_a_time(monkeypatch):
    manager = BluetoothManager()
    entered = threading.Event()
    release = threading.Event()
    results: list[bool] = []

    def slow_refresh() -> bool:
        entered.set()
        release.wait(timeout=1)
        return True

    monkeypatch.setattr(manager, "remove_dualsense_pairing", slow_refresh)
    monkeypatch.setattr(manager, "clear_bluetooth_cache", lambda: True)
    monkeypatch.setattr(manager, "restart_bluetooth_service", lambda: True)
    monkeypatch.setattr("src.bluetooth_utils.time.sleep", lambda _seconds: None)

    first = threading.Thread(target=lambda: results.append(manager.full_bluetooth_reset()))
    first.start()
    assert entered.wait(timeout=1)
    assert manager.is_cleanup_in_progress()

    second_result = manager.full_bluetooth_reset()
    release.set()
    first.join(timeout=1)

    assert second_result is False
    assert results == [True]
    assert not manager.is_cleanup_in_progress()
