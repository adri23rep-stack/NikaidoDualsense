import threading
import time
from types import SimpleNamespace

import src.system_tray as system_tray_module
from src.mouse_to_gyro import MouseGyroSource
from src.system_tray import TrayManager

from src.connection_manager import ConnectionManager
from src.keyboard_gamepad import KeyboardGamepadEngine
from src.light_effects import LightEffectEngine
from src.trigger_engine import TriggerEngine


def test_connection_manager_concurrent_start_creates_one_thread_pair():
    manager = ConnectionManager()
    manager._connection_enabled = False
    gate = threading.Barrier(9)

    def starter():
        gate.wait()
        manager.start()

    workers = [threading.Thread(target=starter) for _ in range(8)]
    for worker in workers:
        worker.start()
    gate.wait()
    for worker in workers:
        worker.join(1.0)

    connection_threads = [
        thread
        for thread in threading.enumerate()
        if thread.name == "ConnectionMonitor" and thread.is_alive()
    ]
    state_threads = [
        thread
        for thread in threading.enumerate()
        if thread.name == "StateMonitor" and thread.is_alive()
    ]
    assert len(connection_threads) == 1
    assert len(state_threads) == 1

    manager.stop()
    assert not manager._running
    assert manager._connection_thread is None
    assert manager._state_thread is None


def test_trigger_animation_concurrent_start_uses_one_worker():
    engine = TriggerEngine()
    gate = threading.Barrier(9)
    seen_threads = []
    seen_lock = threading.Lock()

    def starter():
        gate.wait()
        engine._start_animation()
        with seen_lock:
            seen_threads.append(engine._animation_thread)

    workers = [threading.Thread(target=starter) for _ in range(8)]
    for worker in workers:
        worker.start()
    gate.wait()
    for worker in workers:
        worker.join(1.0)

    assert seen_threads
    assert len({id(thread) for thread in seen_threads}) == 1
    assert engine._animation_thread is not None
    assert engine._animation_thread.is_alive()

    engine._stop_animation()
    time.sleep(0.01)
    assert engine._animation_thread is None
    assert not engine._animation_running


class _ConcurrentMouseSource(MouseGyroSource):
    def __init__(self):
        super().__init__()
        self.capture_starts = 0
        self.max_active_captures = 0
        self._active_captures = 0
        self._capture_counter_lock = threading.Lock()

    def is_available(self):
        return True

    def _capture_loop(self):
        with self._capture_counter_lock:
            self.capture_starts += 1
            self._active_captures += 1
            self.max_active_captures = max(
                self.max_active_captures,
                self._active_captures,
            )
        self._backend = "test"
        self._start_ok = True
        self._ready.set()
        try:
            while self._running:
                time.sleep(0.002)
        finally:
            with self._capture_counter_lock:
                self._active_captures -= 1
            self._running = False
            self._ready.set()

    def _watchdog_loop(self, stop_event):
        stop_event.wait()

    def _wake_capture_thread(self):
        return None

    def _restore_cursor_position(self):
        return None


def test_mouse_capture_concurrent_start_creates_one_capture_worker():
    source = _ConcurrentMouseSource()
    gate = threading.Barrier(9)
    results = []
    result_lock = threading.Lock()

    def starter():
        gate.wait()
        result = source.start()
        with result_lock:
            results.append(result)

    workers = [threading.Thread(target=starter) for _ in range(8)]
    for worker in workers:
        worker.start()
    gate.wait()
    for worker in workers:
        worker.join(1.0)

    assert results == [True] * 8
    assert source.capture_starts == 1
    assert source.max_active_captures == 1

    source.stop()
    assert source._thread is None
    assert source._watchdog_thread is None


def test_mouse_capture_concurrent_delayed_start_uses_one_countdown():
    source = _ConcurrentMouseSource()
    gate = threading.Barrier(9)
    threads = []
    threads_lock = threading.Lock()

    def starter():
        gate.wait()
        assert source.start_delayed(0.5)
        with threads_lock:
            threads.append(source._activation_thread)

    workers = [threading.Thread(target=starter) for _ in range(8)]
    for worker in workers:
        worker.start()
    gate.wait()
    for worker in workers:
        worker.join(1.0)

    assert threads
    assert len({id(thread) for thread in threads}) == 1
    assert source.is_activation_pending()
    source.cancel_delayed_start()
    assert source._activation_thread is None


def test_system_tray_concurrent_start_creates_one_icon(monkeypatch):
    instances = []

    class FakeIcon:
        def __init__(self, *_args, **_kwargs):
            self.stop_event = threading.Event()
            self.run_started = threading.Event()
            instances.append(self)

        def run(self):
            self.run_started.set()
            self.stop_event.wait()

        def stop(self):
            self.stop_event.set()

    monkeypatch.setattr(system_tray_module, "PYSTRAY_AVAILABLE", True)
    monkeypatch.setattr(system_tray_module, "PIL_AVAILABLE", True)
    monkeypatch.setattr(
        system_tray_module,
        "pystray",
        SimpleNamespace(Icon=FakeIcon),
    )

    tray = TrayManager()
    monkeypatch.setattr(tray, "_current_icon_image", lambda: object())
    monkeypatch.setattr(tray, "_build_menu", lambda: object())
    gate = threading.Barrier(9)

    def starter():
        gate.wait()
        tray.start()

    workers = [threading.Thread(target=starter) for _ in range(8)]
    for worker in workers:
        worker.start()
    gate.wait()
    for worker in workers:
        worker.join(1.0)

    assert len(instances) == 1
    assert instances[0].run_started.wait(0.5)
    assert tray.is_visible()

    tray.stop()
    assert tray._thread is None
    assert not tray.is_visible()


class _LingeringThread:
    def __init__(self):
        self.alive = True
        self.join_calls = 0

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.join_calls += 1


def test_connection_manager_keeps_lingering_worker_and_rejects_restart():
    manager = ConnectionManager()
    manager._connection_enabled = False
    lingering = _LingeringThread()
    manager._connection_thread = lingering

    manager.stop()

    assert lingering.join_calls == 1
    assert manager._connection_thread is lingering
    manager.start()
    assert not manager._running
    assert manager._connection_thread is lingering

    lingering.alive = False
    manager.start()
    assert manager._running
    assert manager._connection_thread is not lingering
    manager.stop()


class _BlockingHotkeySource(MouseGyroSource):
    def __init__(self):
        super().__init__()
        self.hotkey_starts = 0
        self.hotkey_releases = []
        self.hotkey_started = threading.Event()

    def is_available(self):
        return True

    def _hotkey_loop(self, stop_event):
        release = threading.Event()
        with self._lock:
            self.hotkey_starts += 1
            self.hotkey_releases.append(release)
            self.hotkey_started.set()
        try:
            release.wait()
        finally:
            current = threading.current_thread()
            with self._lock:
                if self._hotkey_thread is current:
                    self._hotkey_thread = None


def test_mouse_hotkey_does_not_restart_over_listener_still_closing():
    source = _BlockingHotkeySource()
    assert source.arm_hotkey_toggle(True)
    assert source.hotkey_started.wait(0.5)
    first_thread = source._hotkey_thread

    assert source.arm_hotkey_toggle(False)
    assert first_thread is not None and first_thread.is_alive()
    assert source._hotkey_thread is first_thread
    assert not source.arm_hotkey_toggle(True)
    assert source.hotkey_starts == 1

    source.hotkey_releases[0].set()
    first_thread.join(0.5)
    assert not first_thread.is_alive()

    source.hotkey_started.clear()
    assert source.arm_hotkey_toggle(True)
    assert source.hotkey_started.wait(0.5)
    assert source.hotkey_starts == 2
    source.hotkey_releases[1].set()
    source.arm_hotkey_toggle(False)


def test_keybridge_rejects_restart_while_old_worker_is_alive():
    engine = KeyboardGamepadEngine(object())
    lingering = _LingeringThread()
    engine._thread = lingering
    engine._running = False

    assert not engine.start()
    assert engine._thread is lingering
    assert "todavía se está cerrando" in engine.last_error


def test_light_engine_retains_lingering_worker_before_restart():
    engine = LightEffectEngine()
    lingering = _LingeringThread()
    engine._thread = lingering
    engine._running = False

    engine.stop()
    assert engine._thread is lingering
    engine.start()
    assert engine._thread is lingering

    lingering.alive = False
    engine.start()
    assert engine._thread is not lingering
    engine.stop()


def test_trigger_engine_retains_lingering_animation_before_restart():
    engine = TriggerEngine()
    lingering = _LingeringThread()
    engine._animation_thread = lingering
    engine._animation_running = False

    engine._stop_animation()
    assert engine._animation_thread is lingering
    engine._start_animation()
    assert engine._animation_thread is lingering

    lingering.alive = False
    engine._start_animation()
    assert engine._animation_thread is not lingering
    engine._stop_animation()
