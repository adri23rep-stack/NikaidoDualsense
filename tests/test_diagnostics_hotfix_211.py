from types import SimpleNamespace
from unittest.mock import patch

from src.connection_manager import ConnectionManager
from src.diagnostics import DiagnosticEngine
from src.gyro_engine import GyroEngine


def _state(sequence: int, *, cross: bool = False):
    return SimpleNamespace(
        sequence=sequence,
        source="raw_hid",
        monotonic_ns=1_000_000_000,
        buttons={"cross": cross},
        left_stick_x=128,
        left_stick_y=128,
        right_stick_x=128,
        right_stick_y=128,
        left_trigger=0,
        right_trigger=0,
        gyro_pitch=0,
        gyro_yaw=0,
        gyro_roll=0,
        accel_x=0,
        accel_y=0,
        accel_z=0,
    )


def test_sequence_jumps_estimate_device_rate_without_false_packet_loss():
    manager = ConnectionManager()
    times = [10.000, 10.016, 10.032]
    ns = [10_000_000_000, 10_016_000_000, 10_032_000_000]
    with patch("src.connection_manager.time.perf_counter", side_effect=times), patch(
        "src.connection_manager.time.perf_counter_ns", side_effect=ns
    ):
        manager._record_diagnostics(_state(0), True, 0.0, 0.0001, 0.0002, 0.0003)
        manager._record_diagnostics(_state(4), True, 0.0, 0.0001, 0.0002, 0.0003)
        manager._record_diagnostics(_state(8, cross=True), True, 0.0, 0.0001, 0.0002, 0.0003)

    snapshot = manager.get_diagnostics_snapshot()
    assert 249.0 <= snapshot["device_report_hz"] <= 251.0
    assert snapshot["coalesced_reports"] == 6
    assert snapshot["confirmed_lost_reports"] == 0
    assert snapshot["lost_reports"] == 0
    assert snapshot["button_edge_count"] == 1
    assert snapshot["button_edge_p95_ms"] == 0.3


def test_health_treats_coalescing_and_passthrough_calibration_as_information():
    health, issues, advisories = DiagnosticEngine._health(
        {
            "connected": True,
            "device_report_hz": 250.0,
            "processing_hz": 125.0,
            "fresh_snapshot_hz": 67.0,
            "coalesced_reports": 20_000,
            "read_failures": 0,
            "pipeline_p95_ms": 0.6,
        },
        {"last_error": ""},
        {"enabled": True, "mode": "passthrough_ds4", "calibrated": False},
        [],
    )
    assert health == "excellent"
    assert issues == []
    assert any("calibración" in item for item in advisories)


class _FakeConnection:
    def on_state_update(self, callback):
        self.callback = callback

    def get_last_pipeline_sample(self):
        return {
            "sequence": 9,
            "pipeline_ms": 0.42,
            "button_edge": True,
        }


class _FakeEmulator:
    def get_output_state_snapshot(self):
        return {
            "active": True,
            "mode": "ps4",
            "sequence": 9,
            "buttons": ["cross"],
            "left_stick": (0.0, 0.0),
            "right_stick": (0.0, 0.0),
            "left_trigger": 0,
            "right_trigger": 0,
            "updated_ns": 1_000_420_000,
        }


def test_capture_contains_physical_virtual_and_timing_views():
    connection = _FakeConnection()
    engine = DiagnosticEngine(connection_manager=connection, emulator=_FakeEmulator())
    sample = engine._state_sample(_state(9, cross=True))
    assert sample["physical"]["buttons"] == ["cross"]
    assert sample["virtual"]["buttons"] == ["cross"]
    assert sample["timing"]["pipeline_ms"] == 0.42
    assert sample["timing"]["physical_snapshot_to_vigem_ms"] == 0.42
    # Compatibilidad con lectores 2.1.0.
    assert sample["buttons"] == ["cross"]


def test_gyro_rate_uses_unique_source_sequences_not_callback_bursts():
    engine = GyroEngine()
    engine.start()
    engine.apply_config({"enabled": True, "mode": "passthrough_ds4"}, "rate")
    states = [_state(1), _state(1), _state(2), _state(3)]
    with patch("src.gyro_engine.time.perf_counter", side_effect=[1.0, 1.001, 1.01, 1.02]):
        for item in states:
            engine._on_state_update(item)
    rate = engine.get_telemetry().sample_hz
    assert 99.0 <= rate <= 101.0
    engine.stop()
