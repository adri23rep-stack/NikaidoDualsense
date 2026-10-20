"""Regresiones de desconexión física para Nikaido 2.7.1."""

from __future__ import annotations

import time
from types import SimpleNamespace

from src.connection_manager import (
    ChargingStatus,
    ConnectionManager,
    ConnectionType,
)


class FrozenDualSense:
    def __init__(self, sequence: int = 7, *, valid_report: bool = True) -> None:
        report = [0] * 54
        report[7] = sequence & 0xFF
        report[53] = 5
        self.states = report if valid_report else []
        self.state = SimpleNamespace()
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _connected_manager(controller: FrozenDualSense) -> ConnectionManager:
    manager = ConnectionManager()
    manager.dualsense = controller
    manager._connected = True
    manager._connection_type = ConnectionType.USB
    manager._state.connected = True
    manager._state.connection_type = ConnectionType.USB
    return manager


def test_frozen_raw_report_is_not_treated_as_a_new_read() -> None:
    controller = FrozenDualSense(sequence=17)
    manager = _connected_manager(controller)
    manager._last_raw_sequence = 17
    manager._last_fresh_report = time.monotonic() - manager.STALE_TIMEOUT - 0.2

    disconnects: list[bool] = []
    snapshots = []
    manager.on_disconnect(lambda: disconnects.append(True))
    manager.on_state_update(snapshots.append)

    manager._read_controller_state()

    assert manager.is_connected is False
    assert controller.closed is True
    assert disconnects == [True]
    assert snapshots[-1].connected is False
    assert snapshots[-1].connection_type is ConnectionType.NONE
    assert snapshots[-1].battery_level == 0
    assert snapshots[-1].buttons == {}


def test_new_hid_sequence_refreshes_connection_liveness() -> None:
    controller = FrozenDualSense(sequence=18)
    manager = _connected_manager(controller)
    manager._last_raw_sequence = 17
    old_fresh = time.monotonic() - manager.STALE_TIMEOUT - 0.2
    manager._last_fresh_report = old_fresh

    manager._read_controller_state()

    assert manager.is_connected is True
    assert manager._last_raw_sequence == 18
    assert manager._last_fresh_report > old_fresh
    assert manager.state.sequence == 18
    assert manager.state.battery_level == 55


def test_missing_raw_capture_does_not_keep_a_real_raw_source_alive() -> None:
    controller = FrozenDualSense(valid_report=False)
    manager = _connected_manager(controller)
    manager._raw_report_seen = True
    manager._last_fresh_report = time.monotonic() - manager.STALE_TIMEOUT - 0.2

    manager._read_controller_state()

    assert manager.is_connected is False
    assert controller.closed is True


def test_disconnect_resets_battery_and_charging_state() -> None:
    controller = FrozenDualSense(sequence=5)
    manager = _connected_manager(controller)
    manager._state.battery_level = 90
    manager._state.charging_status = ChargingStatus.CHARGING
    battery_events = []
    manager.on_battery_change(lambda level, status: battery_events.append((level, status)))

    manager._disconnect()

    assert manager.state.battery_level == 0
    assert manager.state.charging_status is ChargingStatus.UNKNOWN
    assert battery_events[-1] == (0, ChargingStatus.UNKNOWN)


def test_disconnected_ui_clears_the_stale_battery_label() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    main_window = (root / "gui" / "main_window.py").read_text(encoding="utf-8")
    dashboard = (root / "gui" / "pages" / "dashboard.py").read_text(encoding="utf-8")

    assert 'self.side_battery.setText("▣ —")' in main_window
    assert "self.dashboard.clear_battery(connected=False)" in main_window
    assert 'self.battery_value.setText("—")' in dashboard


def test_raw_field_that_has_not_produced_a_report_uses_safe_fallback() -> None:
    """Un ``states=None`` inicial no debe provocar una reconexión falsa."""
    controller = FrozenDualSense(valid_report=False)
    controller.states = None
    manager = _connected_manager(controller)
    manager._last_fresh_report = time.monotonic() - manager.STALE_TIMEOUT - 0.2

    manager._read_controller_state()

    assert manager.is_connected is True
    assert controller.closed is False
    assert manager.state.source == "pydualsense_fallback"


def test_announced_raw_capture_must_start_after_the_grace_period() -> None:
    controller = FrozenDualSense(valid_report=False)
    controller.states = None
    manager = _connected_manager(controller)
    manager._raw_report_wait_started = (
        time.monotonic() - manager.RAW_REPORT_STARTUP_GRACE - manager.STALE_TIMEOUT - 0.2
    )
    manager._last_fresh_report = time.monotonic() - manager.STALE_TIMEOUT - 0.2

    manager._read_controller_state()

    assert manager.is_connected is False
    assert controller.closed is True


def test_legacy_controller_without_raw_capture_keeps_safe_fallback() -> None:
    class LegacyDualSense:
        def __init__(self) -> None:
            self.state = SimpleNamespace()
            self.closed = False

        def close(self) -> None:
            self.closed = True

    controller = LegacyDualSense()
    manager = _connected_manager(controller)
    manager._raw_report_wait_started = time.monotonic() - 60.0
    manager._last_fresh_report = time.monotonic() - manager.STALE_TIMEOUT - 0.2

    manager._read_controller_state()

    assert manager.is_connected is True
    assert controller.closed is False
    assert manager.state.source == "pydualsense_fallback"


def test_missing_raw_capture_is_stale_after_first_real_raw_report() -> None:
    controller = FrozenDualSense(valid_report=False)
    manager = _connected_manager(controller)
    manager._raw_report_seen = True
    manager._last_fresh_report = time.monotonic() - manager.STALE_TIMEOUT - 0.2

    manager._read_controller_state()

    assert manager.is_connected is False
    assert controller.closed is True


def test_concurrent_disconnect_closes_controller_only_once() -> None:
    import threading

    class SlowCloseDualSense(FrozenDualSense):
        def __init__(self) -> None:
            super().__init__()
            self.close_count = 0
            self.close_started = threading.Event()
            self.allow_close = threading.Event()

        def close(self) -> None:
            self.close_count += 1
            self.close_started.set()
            self.allow_close.wait(timeout=1)
            self.closed = True

    controller = SlowCloseDualSense()
    manager = _connected_manager(controller)
    disconnects: list[bool] = []
    manager.on_disconnect(lambda: disconnects.append(True))

    first = threading.Thread(target=manager._disconnect)
    second = threading.Thread(target=manager._disconnect)
    first.start()
    assert controller.close_started.wait(timeout=1)
    second.start()
    time.sleep(0.02)
    controller.allow_close.set()
    first.join(timeout=1)
    second.join(timeout=1)

    assert controller.close_count == 1
    assert disconnects == [True]
