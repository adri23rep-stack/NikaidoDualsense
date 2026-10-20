import threading
import time
from types import SimpleNamespace

from src.audio_manager import (
    AudioDeviceInfo,
    AudioEndpointState,
    AudioManager,
    sanitize_audio_config,
)
from src.connection_manager import ConnectionManager
from src.trigger_engine import TriggerEngine, WeaponProfile


def wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


class FakeConnection:
    def __init__(self):
        self.state_callbacks = []
        self.connect_callbacks = []
        self.disconnect_callbacks = []
        self.mic_calls = []

    def on_state_update(self, callback):
        self.state_callbacks.append(callback)

    def on_connect(self, callback):
        self.connect_callbacks.append(callback)

    def on_disconnect(self, callback):
        self.disconnect_callbacks.append(callback)

    def set_microphone_state(self, muted, *, mute_audio=True):
        self.mic_calls.append((bool(muted), bool(mute_audio)))
        return True

    def emit_button(self, pressed):
        state = SimpleNamespace(buttons={"mute": bool(pressed)})
        for callback in list(self.state_callbacks):
            callback(state)

    def emit_connect(self):
        for callback in list(self.connect_callbacks):
            callback("usb")


class FakeBackend:
    def __init__(self):
        self.initialized = False
        self.shutdown_called = False
        self.devices = [
            AudioDeviceInfo("mic-default", "Micrófono principal", True),
            AudioDeviceInfo("mic-headset", "Audífonos", False),
        ]
        self.states = {
            "mic-default": AudioEndpointState("mic-default", "Micrófono principal", False, 72),
            "mic-headset": AudioEndpointState("mic-headset", "Audífonos", False, 55),
        }
        self.mute_writes = []
        self.volume_writes = []
        self.lock = threading.RLock()

    def initialize(self):
        self.initialized = True

    def shutdown(self):
        self.shutdown_called = True

    def list_capture_devices(self, *, force=False):
        return list(self.devices)

    def _id(self, requested):
        return "mic-default" if requested in ("", "default", "missing") else requested

    def get_state(self, requested):
        with self.lock:
            return self.states[self._id(requested)]

    def set_muted(self, requested, muted):
        with self.lock:
            device_id = self._id(requested)
            old = self.states[device_id]
            new = AudioEndpointState(old.device_id, old.name, bool(muted), old.volume)
            self.states[device_id] = new
            self.mute_writes.append((device_id, bool(muted)))
            return new

    def set_volume(self, requested, volume):
        with self.lock:
            device_id = self._id(requested)
            old = self.states[device_id]
            new = AudioEndpointState(old.device_id, old.name, old.muted, int(volume))
            self.states[device_id] = new
            self.volume_writes.append((device_id, int(volume)))
            return new

    def _group_ids(self, *, exclude_dualsense=False):
        return [
            item.id
            for item in self.devices
            if not (exclude_dualsense and item.is_dualsense)
        ]

    def get_group_states(self, *, exclude_dualsense=False):
        with self.lock:
            return [self.states[device_id] for device_id in self._group_ids(
                exclude_dualsense=exclude_dualsense
            )]

    def set_group_muted(self, muted, *, exclude_dualsense=False):
        return [
            self.set_muted(device_id, muted)
            for device_id in self._group_ids(exclude_dualsense=exclude_dualsense)
        ]

    def restore_group_mutes(self, muted_by_id):
        restored = []
        for device_id, muted in muted_by_id.items():
            if device_id in self.states:
                restored.append(self.set_muted(device_id, muted))
        return restored


def test_audio_config_sanitizes_imported_values():
    assert sanitize_audio_config(None) == {
        "enabled": True,
        "button_enabled": True,
        "target_mode": "all",
        "device_id": "default",
        "led_sync": True,
        "apply_volume": False,
        "volume": 100,
        "profile_mute_mode": "keep",
    }
    config = sanitize_audio_config(
        {
            "enabled": 0,
            "button_enabled": [],
            "target_mode": "nuclear",
            "device_id": "x" * 5000,
            "led_sync": 1,
            "apply_volume": "yes",
            "volume": float("inf"),
            "profile_mute_mode": "destroy",
        }
    )
    assert config["enabled"] is False
    assert config["button_enabled"] is False
    assert config["target_mode"] == "all"
    assert len(config["device_id"]) == 1024
    assert config["volume"] == 100
    assert config["profile_mute_mode"] == "keep"


def test_mic_button_toggles_once_per_press_and_syncs_led():
    backend = FakeBackend()
    connection = FakeConnection()
    manager = AudioManager(connection, backend_factory=lambda: backend)
    manager.BUTTON_DEBOUNCE_SECONDS = 0.02
    manager.POLL_INTERVAL = 0.03
    assert manager.start()
    manager.apply_config(
        {"target_mode": "selected", "device_id": "default", "led_sync": True}, "sniper"
    )
    assert wait_until(lambda: manager.get_snapshot()["available"])

    connection.emit_button(True)
    connection.emit_button(True)
    connection.emit_button(True)
    assert wait_until(lambda: manager.get_snapshot()["muted"] is True)
    assert backend.mute_writes == [("mic-default", True)]
    assert connection.mic_calls[-1] == (True, True)

    connection.emit_button(False)
    time.sleep(0.03)
    connection.emit_button(True)
    assert wait_until(lambda: manager.get_snapshot()["muted"] is False)
    assert backend.mute_writes[-1] == ("mic-default", False)
    manager.stop()
    assert backend.shutdown_called


def test_external_windows_mute_is_reflected_on_dualsense_led():
    backend = FakeBackend()
    connection = FakeConnection()
    manager = AudioManager(connection, backend_factory=lambda: backend)
    manager.POLL_INTERVAL = 0.02
    manager.start()
    manager.apply_config({"target_mode": "selected", "led_sync": True}, "default")
    assert wait_until(lambda: manager.get_snapshot()["available"])

    with backend.lock:
        old = backend.states["mic-default"]
        backend.states["mic-default"] = AudioEndpointState(
            old.device_id, old.name, True, old.volume
        )
    assert wait_until(lambda: manager.get_snapshot()["muted"] is True)
    assert wait_until(lambda: connection.mic_calls and connection.mic_calls[-1] == (True, True))
    manager.stop()


def test_profile_can_choose_device_volume_and_initial_mute_state():
    backend = FakeBackend()
    manager = AudioManager(FakeConnection(), backend_factory=lambda: backend)
    manager.POLL_INTERVAL = 0.03
    manager.start()
    manager.apply_config(
        {
            "target_mode": "selected",
            "device_id": "mic-headset",
            "apply_volume": True,
            "volume": 37,
            "profile_mute_mode": "muted",
        },
        "custom_chat",
    )
    assert wait_until(
        lambda: (
            manager.get_snapshot()["active_device_id"] == "mic-headset"
            and manager.get_snapshot()["muted"] is True
            and manager.get_snapshot()["volume"] == 37
        )
    )
    assert backend.volume_writes[-1] == ("mic-headset", 37)
    assert backend.mute_writes[-1] == ("mic-headset", True)
    manager.stop()


def test_led_sync_can_be_disabled_without_disabling_windows_mute():
    backend = FakeBackend()
    connection = FakeConnection()
    manager = AudioManager(connection, backend_factory=lambda: backend)
    manager.POLL_INTERVAL = 0.03
    manager.start()
    manager.apply_config({"target_mode": "selected", "led_sync": False}, "silent_led")
    assert wait_until(lambda: manager.get_snapshot()["available"])
    manager.set_muted(True)
    assert wait_until(lambda: manager.get_snapshot()["muted"] is True)
    assert backend.mute_writes[-1] == ("mic-default", True)
    assert connection.mic_calls[-1] == (False, True)
    manager.stop()


def test_audio_config_roundtrips_in_weapon_profile_and_overrides():
    engine = TriggerEngine(None)
    profile = engine.get_profile("sniper")
    profile.audio_config = {
        "device_id": "mic-headset",
        "volume": 44,
        "apply_volume": True,
        "profile_mute_mode": "unmuted",
    }
    restored = WeaponProfile.from_dict(profile.to_dict())
    assert restored.audio_config["device_id"] == "mic-headset"
    assert restored.audio_config["volume"] == 44
    assert restored.audio_config["profile_mute_mode"] == "unmuted"

    exported = engine.export_profile_overrides()["assault_rifle"]
    assert exported["audio_config"]["device_id"] == "mic-headset"


def test_connection_manager_sets_dualsense_microphone_state_under_io_lock():
    class Audio:
        def __init__(self):
            self.states = []
            self.leds = []

        def setMicrophoneState(self, state):
            self.states.append(bool(state))

        def setMicrophoneLED(self, state):
            self.leds.append(bool(state))

    manager = ConnectionManager.__new__(ConnectionManager)
    manager._io_lock = threading.RLock()
    audio = Audio()
    manager.dualsense = SimpleNamespace(audio=audio)

    assert manager.set_microphone_state(True)
    assert audio.states == [True]
    assert manager.set_microphone_state(False, mute_audio=False)
    assert audio.leds == [False]


def test_pycaw_backend_wraps_raw_default_microphone_from_current_api():
    from src.audio_manager import PycawCaptureBackend

    class Endpoint:
        def __init__(self):
            self.muted = False
            self.volume = 0.64

        def GetMute(self):
            return self.muted

        def SetMute(self, value, _context):
            self.muted = bool(value)

        def GetMasterVolumeLevelScalar(self):
            return self.volume

        def SetMasterVolumeLevelScalar(self, value, _context):
            self.volume = float(value)

    class RawDevice:
        pass

    class WrappedDevice:
        def __init__(self):
            self.id = "raw-default"
            self.FriendlyName = "Micrófono COM"
            self._endpoint = Endpoint()

        @property
        def EndpointVolume(self):
            return self._endpoint

    raw = RawDevice()
    wrapped = WrappedDevice()

    class Utilities:
        create_calls = 0

        @staticmethod
        def GetMicrophone():
            return raw

        @staticmethod
        def CreateDevice(device):
            assert device is raw
            Utilities.create_calls += 1
            return wrapped

        @staticmethod
        def GetAllDevices(**_kwargs):
            return [raw]

    backend = PycawCaptureBackend()
    backend._AudioUtilities = Utilities
    backend._capture_flow = 1
    backend._active_state = 1

    devices = backend.list_capture_devices(force=True)
    assert devices == [AudioDeviceInfo("raw-default", "Micrófono COM", True)]
    assert backend.get_state("default") == AudioEndpointState(
        "raw-default", "Micrófono COM", False, 64
    )
    assert Utilities.create_calls >= 2


def test_live_profile_edit_does_not_reapply_mute_or_profile_volume():
    backend = FakeBackend()
    connection = FakeConnection()
    manager = AudioManager(
        connection,
        {
            "target_mode": "selected",
            "device_id": "mic-headset",
            "profile_mute_mode": "muted",
            "apply_volume": True,
            "volume": 31,
        },
        backend_factory=lambda: backend,
    )
    manager.POLL_INTERVAL = 0.03
    manager.start()
    assert wait_until(lambda: manager.get_snapshot()["muted"] is True)
    assert backend.mute_writes == [("mic-headset", True)]
    assert backend.volume_writes == [("mic-headset", 31)]

    manager.apply_config(
        {
            "target_mode": "selected",
            "device_id": "mic-headset",
            "profile_mute_mode": "muted",
            "apply_volume": True,
            "volume": 88,
            "led_sync": False,
        },
        "chat",
        apply_profile_state=False,
    )
    assert wait_until(lambda: connection.mic_calls and connection.mic_calls[-1] == (False, True))
    assert backend.mute_writes == [("mic-headset", True)]
    assert backend.volume_writes == [("mic-headset", 31)]
    manager.stop()


def test_prestart_profile_configuration_is_applied_exactly_once():
    backend = FakeBackend()
    manager = AudioManager(FakeConnection(), backend_factory=lambda: backend)
    manager.apply_config(
        {"target_mode": "selected", "device_id": "mic-headset", "profile_mute_mode": "muted"},
        "voice_chat",
    )
    manager.start()
    assert wait_until(lambda: manager.get_snapshot()["muted"] is True)
    assert backend.mute_writes == [("mic-headset", True)]
    manager.stop()


def test_disabling_audio_stops_button_and_restores_controller_mic_state():
    backend = FakeBackend()
    connection = FakeConnection()
    manager = AudioManager(connection, backend_factory=lambda: backend)
    manager.BUTTON_DEBOUNCE_SECONDS = 0.01
    manager.POLL_INTERVAL = 0.03
    manager.start()
    assert wait_until(lambda: manager.get_snapshot()["available"])
    manager.set_muted(True)
    assert wait_until(lambda: connection.mic_calls and connection.mic_calls[-1] == (True, True))

    manager.apply_config({"enabled": False, "led_sync": True}, "disabled")
    assert wait_until(lambda: connection.mic_calls[-1] == (False, True))
    writes_before = list(backend.mute_writes)
    connection.emit_button(False)
    connection.emit_button(True)
    time.sleep(0.06)
    assert backend.mute_writes == writes_before
    manager.stop()


def test_connection_manager_falls_back_to_led_when_full_mic_state_fails():
    class Audio:
        def __init__(self):
            self.leds = []

        def setMicrophoneState(self, _state):
            raise RuntimeError("not supported")

        def setMicrophoneLED(self, state):
            self.leds.append(bool(state))

    manager = ConnectionManager.__new__(ConnectionManager)
    manager._io_lock = threading.RLock()
    audio = Audio()
    manager.dualsense = SimpleNamespace(audio=audio)

    assert manager.set_microphone_state(True)
    assert audio.leds == [True]


def test_failed_controller_sync_is_retried_instead_of_cached():
    class FlakyConnection(FakeConnection):
        def __init__(self):
            super().__init__()
            self.results = [False, True]

        def set_microphone_state(self, muted, *, mute_audio=True):
            self.mic_calls.append((bool(muted), bool(mute_audio)))
            return self.results.pop(0)

    connection = FlakyConnection()
    manager = AudioManager(connection, backend_factory=FakeBackend)
    manager._sync_controller(True, True)
    manager._sync_controller(True, True)
    assert connection.mic_calls == [(True, True), (True, True)]


def test_missing_saved_microphone_falls_back_without_forgetting_selection():
    backend = FakeBackend()
    manager = AudioManager(
        FakeConnection(),
        {"target_mode": "selected", "device_id": "missing"},
        backend_factory=lambda: backend,
    )
    manager.POLL_INTERVAL = 0.03
    manager.start()
    assert wait_until(lambda: manager.get_snapshot()["available"])
    snapshot = manager.get_snapshot()
    assert snapshot["selected_device_id"] == "missing"
    assert snapshot["active_device_id"] == "mic-default"
    assert snapshot["using_fallback"] is True
    manager.stop()


def test_pycaw_shutdown_releases_endpoint_wrappers_before_com_uninitialize():
    from src.audio_manager import PycawCaptureBackend

    calls = []

    class TrackedDevices(list):
        def clear(self):
            calls.append("devices")
            super().clear()

    class Comtypes:
        @staticmethod
        def CoUninitialize():
            calls.append("com")

    backend = PycawCaptureBackend()
    backend._devices = TrackedDevices([object()])
    backend._AudioUtilities = object()
    backend._comtypes = Comtypes
    backend._devices_at = 123.0
    backend._missing_device_retry_at["missing"] = 456.0

    backend.shutdown()

    assert calls == ["devices", "com"]
    assert backend._devices == []
    assert backend._devices_at == 0.0
    assert backend._missing_device_retry_at == {}
    assert backend._AudioUtilities is None
    assert backend._comtypes is None


def test_stop_during_slow_com_initialization_cannot_reenable_mic_after_close():
    entered = threading.Event()
    release = threading.Event()

    class SlowBackend(FakeBackend):
        def initialize(self):
            entered.set()
            assert release.wait(2.0)
            self.initialized = True

    backend = SlowBackend()
    connection = FakeConnection()
    manager = AudioManager(
        connection,
        {"profile_mute_mode": "muted", "led_sync": True},
        backend_factory=lambda: backend,
    )
    assert manager.start()
    assert entered.wait(1.0)

    stopped = threading.Event()

    def stop_manager():
        manager.stop()
        stopped.set()

    closer = threading.Thread(target=stop_manager)
    closer.start()
    assert wait_until(manager._stop_event.is_set)
    release.set()
    closer.join(timeout=2.0)

    assert stopped.is_set()
    assert backend.shutdown_called
    assert not any(muted for muted, _mute_audio in connection.mic_calls)
    assert connection.mic_calls[-1] == (False, True)


def test_global_mute_restores_each_microphone_previous_state():
    backend = FakeBackend()
    backend.states["mic-headset"] = AudioEndpointState(
        "mic-headset", "Audífonos", True, 55
    )
    connection = FakeConnection()
    manager = AudioManager(
        connection,
        {"target_mode": "all", "led_sync": True},
        backend_factory=lambda: backend,
    )
    manager.POLL_INTERVAL = 0.02
    manager.start()
    assert wait_until(lambda: manager.get_snapshot()["target_count"] == 2)

    manager.toggle_mute()
    assert wait_until(lambda: manager.get_snapshot()["muted"] is True)
    assert backend.states["mic-default"].muted is True
    assert backend.states["mic-headset"].muted is True
    assert manager.get_snapshot()["restore_pending"] is True

    manager.toggle_mute()
    assert wait_until(lambda: manager.get_snapshot()["muted"] is False)
    assert backend.states["mic-default"].muted is False
    assert backend.states["mic-headset"].muted is True
    assert manager.get_snapshot()["partially_muted"] is True
    assert manager.get_snapshot()["restore_pending"] is False
    manager.stop()


def test_global_mute_except_dualsense_leaves_controller_input_active_and_uses_led_only():
    backend = FakeBackend()
    backend.devices.append(
        AudioDeviceInfo("mic-dualsense", "Micrófono (Wireless Controller)", False, True)
    )
    backend.states["mic-dualsense"] = AudioEndpointState(
        "mic-dualsense", "Micrófono (Wireless Controller)", False, 80
    )
    connection = FakeConnection()
    manager = AudioManager(
        connection,
        {"target_mode": "all_except_dualsense", "led_sync": True},
        backend_factory=lambda: backend,
    )
    manager.POLL_INTERVAL = 0.02
    manager.start()
    assert wait_until(lambda: manager.get_snapshot()["target_count"] == 2)

    manager.set_muted(True)
    assert wait_until(lambda: manager.get_snapshot()["muted"] is True)
    assert backend.states["mic-default"].muted is True
    assert backend.states["mic-headset"].muted is True
    assert backend.states["mic-dualsense"].muted is False
    assert connection.mic_calls[-1] == (True, False)
    manager.stop()


def test_global_poll_reports_partial_mute_without_lighting_controller_led():
    backend = FakeBackend()
    backend.states["mic-headset"] = AudioEndpointState(
        "mic-headset", "Audífonos", True, 55
    )
    connection = FakeConnection()
    manager = AudioManager(
        connection,
        {"target_mode": "all", "led_sync": True},
        backend_factory=lambda: backend,
    )
    manager.POLL_INTERVAL = 0.02
    manager.start()
    assert wait_until(lambda: manager.get_snapshot()["partially_muted"] is True)
    snapshot = manager.get_snapshot()
    assert snapshot["muted"] is False
    assert snapshot["muted_count"] == 1
    assert snapshot["target_count"] == 2
    assert connection.mic_calls[-1] == (False, True)
    manager.stop()


def test_changing_global_target_restores_previous_global_session():
    backend = FakeBackend()
    manager = AudioManager(
        FakeConnection(),
        {"target_mode": "all"},
        backend_factory=lambda: backend,
    )
    manager.POLL_INTERVAL = 0.02
    manager.start()
    assert wait_until(lambda: manager.get_snapshot()["available"])
    manager.set_muted(True)
    assert wait_until(lambda: manager.get_snapshot()["restore_pending"] is True)

    manager.apply_config(
        {"target_mode": "all_except_dualsense"},
        "changed",
        apply_profile_state=False,
    )
    assert wait_until(
        lambda: manager.get_snapshot()["target_mode"] == "all_except_dualsense"
    )
    assert wait_until(
        lambda: not backend.states["mic-default"].muted
        and not backend.states["mic-headset"].muted
    )
    assert manager.get_snapshot()["restore_pending"] is False
    manager.stop()


def test_dualsense_audio_name_detection_matches_common_windows_names():
    from src.audio_manager import is_dualsense_audio_name

    assert is_dualsense_audio_name("Micrófono (Wireless Controller)")
    assert is_dualsense_audio_name("DualSense Wireless Controller")
    assert not is_dualsense_audio_name("Micrófono USB HyperX")


def test_global_mute_absorbs_new_microphone_and_restores_it_after_hotplug():
    backend = FakeBackend()
    manager = AudioManager(
        FakeConnection(),
        {"target_mode": "all"},
        backend_factory=lambda: backend,
    )
    manager.POLL_INTERVAL = 0.02
    manager.start()
    assert wait_until(lambda: manager.get_snapshot()["target_count"] == 2)
    manager.set_muted(True)
    assert wait_until(lambda: manager.get_snapshot()["muted"] is True)

    with backend.lock:
        backend.devices.append(AudioDeviceInfo("mic-webcam", "Webcam", False, False))
        backend.states["mic-webcam"] = AudioEndpointState(
            "mic-webcam", "Webcam", False, 60
        )
    assert wait_until(lambda: backend.states["mic-webcam"].muted is True)
    assert manager.get_snapshot()["target_count"] == 3

    manager.set_muted(False)
    assert wait_until(lambda: manager.get_snapshot()["restore_pending"] is False)
    assert backend.states["mic-default"].muted is False
    assert backend.states["mic-headset"].muted is False
    assert backend.states["mic-webcam"].muted is False
    manager.stop()


def test_global_session_remutes_endpoint_reenabled_from_windows():
    backend = FakeBackend()
    manager = AudioManager(
        FakeConnection(),
        {"target_mode": "all"},
        backend_factory=lambda: backend,
    )
    manager.POLL_INTERVAL = 0.02
    manager.start()
    assert wait_until(lambda: manager.get_snapshot()["available"])
    manager.set_muted(True)
    assert wait_until(lambda: manager.get_snapshot()["muted"] is True)

    with backend.lock:
        old = backend.states["mic-headset"]
        backend.states["mic-headset"] = AudioEndpointState(
            old.device_id, old.name, False, old.volume
        )
    assert wait_until(lambda: backend.states["mic-headset"].muted is True)
    manager.set_muted(False)
    assert wait_until(lambda: manager.get_snapshot()["restore_pending"] is False)
    assert backend.states["mic-headset"].muted is False
    manager.stop()


def test_pycaw_group_operations_exclude_dualsense_and_restore_exact_ids():
    from src.audio_manager import PycawCaptureBackend

    class Endpoint:
        def __init__(self, muted=False, volume=0.5):
            self.muted = muted
            self.volume = volume

        def GetMute(self):
            return self.muted

        def SetMute(self, muted, _context):
            self.muted = bool(muted)

        def GetMasterVolumeLevelScalar(self):
            return self.volume

    class Device:
        def __init__(self, device_id, name, muted=False):
            self.id = device_id
            self.FriendlyName = name
            self.EndpointVolume = Endpoint(muted)

    regular = Device("regular", "Micrófono USB", False)
    controller = Device("controller", "Micrófono (Wireless Controller)", False)
    backend = PycawCaptureBackend()
    backend._all_unique_devices = lambda force=False: [regular, controller]

    states = backend.set_group_muted(True, exclude_dualsense=True)
    assert [state.device_id for state in states] == ["regular"]
    assert regular.EndpointVolume.muted is True
    assert controller.EndpointVolume.muted is False

    restored = backend.restore_group_mutes({"regular": False, "missing": True})
    assert [state.device_id for state in restored] == ["regular"]
    assert regular.EndpointVolume.muted is False


def test_global_device_listing_still_works_without_windows_default_endpoint():
    from src.audio_manager import PycawCaptureBackend

    class Endpoint:
        def GetMute(self):
            return 0

        def GetMasterVolumeLevelScalar(self):
            return 0.5

    class Device:
        id = "usb"
        FriendlyName = "Micrófono USB"
        EndpointVolume = Endpoint()

    class Utilities:
        @staticmethod
        def GetMicrophone():
            raise RuntimeError("sin predeterminado")

        @staticmethod
        def GetAllDevices(**_kwargs):
            return [Device()]

        @staticmethod
        def CreateDevice(device):
            return device

    backend = PycawCaptureBackend()
    backend._AudioUtilities = Utilities
    backend._capture_flow = 1
    backend._active_state = 1

    assert backend.list_capture_devices(force=True) == [
        AudioDeviceInfo("usb", "Micrófono USB", False, False)
    ]
    assert backend.get_group_states() == [
        AudioEndpointState("usb", "Micrófono USB", False, 50)
    ]


def test_controller_global_mute_emulates_windows_mic_key_and_preserves_restore_map():
    backend = FakeBackend()
    backend.states["mic-headset"] = AudioEndpointState(
        "mic-headset", "Audífonos", True, 55
    )
    connection = FakeConnection()
    key_calls = []

    def send_mic_key():
        key_calls.append(True)
        # Emula lo que puede hacer la tecla física antes de que Nikaido
        # refuerce el estado sobre todos los endpoints.
        with backend.lock:
            old = backend.states["mic-default"]
            backend.states["mic-default"] = AudioEndpointState(
                old.device_id, old.name, not old.muted, old.volume
            )
        return True

    manager = AudioManager(
        connection,
        {"target_mode": "all", "led_sync": True},
        backend_factory=lambda: backend,
        microphone_key_sender=send_mic_key,
    )
    manager.BUTTON_DEBOUNCE_SECONDS = 0.01
    manager.POLL_INTERVAL = 0.02
    manager.start()
    assert wait_until(lambda: manager.get_snapshot()["target_count"] == 2)

    connection.emit_button(True)
    assert wait_until(lambda: manager.get_snapshot()["muted"] is True)
    assert len(key_calls) == 1
    assert manager.get_snapshot()["keyboard_mic_key_sent"] is True
    assert manager.get_snapshot()["last_button_action"] == "windows_microphone_mute_key"
    assert backend.states["mic-default"].muted is True
    assert backend.states["mic-headset"].muted is True
    assert connection.mic_calls[-1] == (True, True)

    connection.emit_button(False)
    time.sleep(0.02)
    connection.emit_button(True)
    assert wait_until(lambda: manager.get_snapshot()["restore_pending"] is False)
    assert len(key_calls) == 2
    assert backend.states["mic-default"].muted is False
    assert backend.states["mic-headset"].muted is True
    manager.stop()


def test_programmatic_global_toggle_does_not_emit_keyboard_mic_key():
    backend = FakeBackend()
    key_calls = []
    manager = AudioManager(
        FakeConnection(),
        {"target_mode": "all"},
        backend_factory=lambda: backend,
        microphone_key_sender=lambda: key_calls.append(True) or True,
    )
    manager.POLL_INTERVAL = 0.02
    manager.start()
    assert wait_until(lambda: manager.get_snapshot()["available"])

    manager.toggle_mute()
    assert wait_until(lambda: manager.get_snapshot()["muted"] is True)
    assert key_calls == []
    assert manager.get_snapshot()["last_button_action"] == "direct_audio"
    manager.stop()


def test_global_except_dualsense_keeps_direct_audio_path_for_controller_button():
    backend = FakeBackend()
    connection = FakeConnection()
    key_calls = []
    manager = AudioManager(
        connection,
        {"target_mode": "all_except_dualsense"},
        backend_factory=lambda: backend,
        microphone_key_sender=lambda: key_calls.append(True) or True,
    )
    manager.BUTTON_DEBOUNCE_SECONDS = 0.01
    manager.POLL_INTERVAL = 0.02
    manager.start()
    assert wait_until(lambda: manager.get_snapshot()["available"])

    connection.emit_button(True)
    assert wait_until(lambda: manager.get_snapshot()["muted"] is True)
    assert key_calls == []
    assert connection.mic_calls[-1] == (True, False)
    manager.stop()


def test_controller_global_key_still_works_when_core_audio_backend_is_unavailable():
    class BrokenBackend:
        def initialize(self):
            raise RuntimeError("COM roto")

        def shutdown(self):
            pass

    connection = FakeConnection()
    key_calls = []
    manager = AudioManager(
        connection,
        {"target_mode": "all", "led_sync": True},
        backend_factory=BrokenBackend,
        microphone_key_sender=lambda: key_calls.append(True) or True,
    )
    manager.BUTTON_DEBOUNCE_SECONDS = 0.01
    manager.RETRY_INTERVAL = 10.0
    manager.start()
    assert wait_until(lambda: "COM roto" in manager.get_snapshot()["error"])

    connection.emit_button(True)
    assert wait_until(lambda: len(key_calls) == 1)
    snapshot = manager.get_snapshot()
    assert snapshot["available"] is True
    assert snapshot["muted"] is True
    assert snapshot["keyboard_mic_key_sent"] is True
    assert snapshot["active_device_id"] == "windows-microphone-mute-key"
    assert connection.mic_calls[-1] == (True, True)

    connection.emit_button(False)
    time.sleep(0.02)
    connection.emit_button(True)
    assert wait_until(lambda: len(key_calls) == 2)
    assert manager.get_snapshot()["muted"] is False
    assert connection.mic_calls[-1] == (False, True)
    manager.stop()
