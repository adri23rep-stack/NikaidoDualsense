import time

from src.virtual_feedback import VirtualFeedbackBridge, sanitize_feedback_config


class EmulatorStub:
    def __init__(self):
        self.callbacks = []

    def on_feedback(self, callback):
        self.callbacks.append(callback)

    def remove_feedback_callback(self, callback):
        self.callbacks.remove(callback)

    def emit(self, large, small):
        for callback in tuple(self.callbacks):
            callback({"large_motor": large, "small_motor": small})


class ConnectionStub:
    def __init__(self):
        self.values = []

    def set_rumble(self, left, right):
        self.values.append((left, right))


def wait_until(predicate, timeout=0.8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_feedback_bridge_scales_and_times_out_safely():
    emulator = EmulatorStub()
    connection = ConnectionStub()
    bridge = VirtualFeedbackBridge(
        emulator,
        connection,
        {
            "enabled": True,
            "strength": 0.5,
            "large_motor_scale": 1.0,
            "small_motor_scale": 2.0,
            "smoothing_ms": 0,
            "idle_timeout_ms": 100,
        },
    )
    bridge.start()
    emulator.emit(200, 50)
    assert wait_until(lambda: (100, 50) in connection.values)
    assert wait_until(lambda: connection.values and connection.values[-1] == (0, 0))
    snapshot = bridge.get_diagnostics_snapshot()
    assert snapshot["received"] == 1
    assert snapshot["timed_out"] is True
    bridge.stop()
    assert emulator.callbacks == []
    assert connection.values[-1] == (0, 0)


def test_feedback_configuration_is_bounded_and_can_be_disabled():
    config = sanitize_feedback_config(
        {
            "strength": 99,
            "large_motor_scale": -3,
            "small_motor_scale": "bad",
            "smoothing_ms": 999,
            "idle_timeout_ms": 1,
            "minimum_output": 999,
        }
    )
    assert config["strength"] == 2.0
    assert config["large_motor_scale"] == 0.0
    assert config["small_motor_scale"] == 1.0
    assert config["smoothing_ms"] == 250
    assert config["idle_timeout_ms"] == 100
    assert config["minimum_output"] == 80


def test_disabled_bridge_neutralizes_after_feedback():
    emulator = EmulatorStub()
    connection = ConnectionStub()
    bridge = VirtualFeedbackBridge(emulator, connection, {"smoothing_ms": 0})
    bridge.start()
    emulator.emit(255, 255)
    assert wait_until(lambda: connection.values and connection.values[-1] == (255, 255))
    bridge.set_enabled(False)
    assert wait_until(lambda: connection.values and connection.values[-1] == (0, 0))
    bridge.stop()


def test_feedback_bridge_can_restart_and_register_callback_again():
    emulator = EmulatorStub()
    connection = ConnectionStub()
    bridge = VirtualFeedbackBridge(emulator, connection, {"smoothing_ms": 0})

    bridge.start()
    emulator.emit(80, 40)
    assert wait_until(lambda: connection.values and connection.values[-1] == (80, 40))
    bridge.stop()
    assert emulator.callbacks == []

    connection.values.clear()
    bridge.start()
    assert len(emulator.callbacks) == 1
    emulator.emit(120, 60)
    assert wait_until(lambda: connection.values and connection.values[-1] == (120, 60))
    bridge.stop()


def test_feedback_bridge_concurrent_restart_creates_one_worker_and_callback():
    import threading

    emulator = EmulatorStub()
    bridge = VirtualFeedbackBridge(emulator, ConnectionStub(), {"smoothing_ms": 0})
    bridge.stop()
    gate = threading.Barrier(9)

    def starter():
        gate.wait()
        bridge.start()

    workers = [threading.Thread(target=starter) for _ in range(8)]
    for worker in workers:
        worker.start()
    gate.wait()
    for worker in workers:
        worker.join(1.0)

    assert len(emulator.callbacks) == 1
    assert bridge._thread is not None and bridge._thread.is_alive()
    bridge.stop()


class _LingeringFeedbackThread:
    def __init__(self):
        self.alive = True
        self.join_calls = 0

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.join_calls += 1


def test_feedback_bridge_does_not_clear_or_restart_lingering_worker():
    emulator = EmulatorStub()
    bridge = VirtualFeedbackBridge(emulator, ConnectionStub(), {"smoothing_ms": 0})
    lingering = _LingeringFeedbackThread()
    bridge._thread = lingering

    bridge.stop()
    assert lingering.join_calls == 1
    assert bridge._thread is lingering
    assert emulator.callbacks == []

    bridge.start()
    assert bridge._thread is lingering
    assert emulator.callbacks == []

    lingering.alive = False
    bridge.start()
    assert bridge._thread is not lingering
    assert len(emulator.callbacks) == 1
    bridge.stop()
