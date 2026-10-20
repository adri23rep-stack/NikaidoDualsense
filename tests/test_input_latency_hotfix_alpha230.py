import threading
from types import SimpleNamespace

from src.connection_manager import ConnectionManager


def _report(sequence: int = 0):
    data = [0] * 64
    data[0] = 1
    data[7] = sequence & 0xFF
    data[8] = 8  # dpad neutral
    return data


def test_peek_raw_sequence_reads_only_latest_counter():
    manager = ConnectionManager()
    manager.dualsense = SimpleNamespace(states=_report(257))
    assert manager._peek_raw_sequence() == 1

    manager.dualsense.states = [0] * 4
    assert manager._peek_raw_sequence() is None


def test_realtime_pipeline_runs_after_releasing_physical_io_lock():
    manager = ConnectionManager()
    manager.dualsense = SimpleNamespace(
        states=_report(12),
        state=SimpleNamespace(),
    )
    manager._connected = True
    manager.emulator.update_from_dualsense = lambda _state: None
    lock_was_free = []

    def realtime_callback(_state):
        acquired = []

        def worker():
            got_lock = manager._io_lock.acquire(timeout=0.1)
            acquired.append(got_lock)
            if got_lock:
                manager._io_lock.release()

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(timeout=0.2)
        lock_was_free.append(bool(acquired and acquired[0]))

    manager.on_realtime_state_update(realtime_callback)
    manager._read_controller_state()

    assert lock_was_free == [True]


def test_low_latency_loop_processes_new_sequence_before_heartbeat():
    manager = ConnectionManager()
    manager.dualsense = SimpleNamespace(states=_report(1), state=SimpleNamespace())
    manager._connected = True
    manager._running = True
    manager.emulator.is_active = True
    manager.emulator.gamepad = object()

    sequences = iter([1, 1, 2, 2, 2])
    current = {"value": 0}
    reads = []

    def peek():
        try:
            current["value"] = next(sequences)
        except StopIteration:
            manager._running = False
        return current["value"]

    def read():
        reads.append(current["value"])
        with manager._lock:
            manager._state.sequence = current["value"]
            manager._state.source = "raw_hid"
        if len(reads) >= 2:
            manager._running = False

    manager._peek_raw_sequence = peek
    manager._read_controller_state = read
    manager._wait_until_state_deadline = lambda _deadline: None
    manager._boost_state_thread_priority = lambda: None

    manager._state_loop()

    assert reads == [1, 2]


def test_low_latency_diagnostics_are_exposed_without_breaking_old_aliases():
    manager = ConnectionManager()
    snapshot = manager.get_diagnostics_snapshot()
    assert snapshot["low_latency_scan_hz"] == 1000.0
    assert snapshot["low_latency_scan_active"] is False
    assert "poll_hz" in snapshot
    assert "unique_hid_hz" in snapshot


def test_physical_output_lock_does_not_block_input_snapshot():
    manager = ConnectionManager()
    manager.dualsense = SimpleNamespace(
        states=_report(21),
        state=SimpleNamespace(),
    )
    manager._connected = True
    manager.emulator.update_from_dualsense = lambda _state: None
    finished = threading.Event()

    manager._io_lock.acquire()
    try:
        thread = threading.Thread(
            target=lambda: (manager._read_controller_state(), finished.set())
        )
        thread.start()
        assert finished.wait(0.25), "La lectura quedó bloqueada por una salida física HID"
        thread.join(timeout=0.25)
    finally:
        manager._io_lock.release()


def test_disconnect_neutralization_cannot_be_overwritten_by_stale_tick():
    manager = ConnectionManager()
    manager.dualsense = SimpleNamespace(
        states=_report(33),
        state=SimpleNamespace(),
        close=lambda: None,
    )
    manager._connected = True
    entered_pipeline = threading.Event()
    continue_pipeline = threading.Event()
    virtual_events = []

    def realtime_callback(_state):
        entered_pipeline.set()
        continue_pipeline.wait(0.5)

    manager.on_realtime_state_update(realtime_callback)
    manager.emulator.update_from_dualsense = lambda _state: virtual_events.append("update")
    manager.emulator.release_all_inputs = lambda: virtual_events.append("neutral")

    reader = threading.Thread(target=manager._read_controller_state)
    reader.start()
    assert entered_pipeline.wait(0.25)

    disconnector = threading.Thread(target=manager._disconnect)
    disconnector.start()
    continue_pipeline.set()
    reader.join(timeout=0.5)
    disconnector.join(timeout=0.5)

    assert not reader.is_alive()
    assert not disconnector.is_alive()
    assert virtual_events == ["neutral"]


def test_hotfix_distribution_metadata_keeps_native_lab_unchanged():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "INPUT_LATENCY_HOTFIX_PROJECT.json").read_text("utf-8"))
    assert payload["distribution_version"] == "3.0.0-alpha.2.3.1"
    assert payload["application_version"] == "2.9.8.10"
    assert payload["native_signing_lab_version"] == "3.0.0-alpha.2.3.0"
    assert payload["native_driver_changed"] is False
