import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

from src.diagnostics import DiagnosticEngine


class FakeConnection:
    def __init__(self):
        self.state_callbacks = []
        self.connect_callbacks = []
        self.disconnect_callbacks = []
        self.error_callbacks = []
        self.emulator = FakeEmulator()

    def on_state_update(self, callback): self.state_callbacks.append(callback)
    def on_connect(self, callback): self.connect_callbacks.append(callback)
    def on_disconnect(self, callback): self.disconnect_callbacks.append(callback)
    def on_error(self, callback): self.error_callbacks.append(callback)

    def emit(self, state):
        for callback in self.state_callbacks:
            callback(state)

    def get_diagnostics_snapshot(self):
        return {
            'connected': True,
            'connection_type': 'usb',
            'poll_hz': 250.0,
            'unique_hid_hz': 250.0,
            'lost_reports': 0,
            'pipeline_avg_ms': 0.22,
            'pipeline_p95_ms': 0.42,
        }


class FakeEmulator:
    def get_diagnostics_snapshot(self):
        return {
            'mode': 'ps4', 'active': True, 'virtual_hz': 250.0,
            'update_avg_ms': 0.08, 'last_error': '',
        }


class FakeGyro:
    def get_telemetry(self):
        return SimpleNamespace(
            mode='mouse', active=True, sample_hz=250.0, calibrated=True,
            output_x=1.0, output_y=2.0, flick_active=False,
        )

    def get_config(self):
        return SimpleNamespace(enabled=True, flick_stick_enabled=True)


class FakeTrigger:
    def get_current_profile(self): return 'test_profile'


def state(index=0):
    return SimpleNamespace(
        sequence=index, source='raw_hid',
        left_stick_x=128, left_stick_y=128,
        right_stick_x=128, right_stick_y=128,
        left_trigger=0, right_trigger=0,
        gyro_pitch=1, gyro_yaw=2, gyro_roll=3,
        accel_x=4, accel_y=5, accel_z=6,
        buttons={'cross': index % 2 == 0},
    )


def test_capture_and_report_are_sanitized(tmp_path):
    connection = FakeConnection()
    engine = DiagnosticEngine(
        connection_manager=connection,
        emulator=connection.emulator,
        gyro_engine=FakeGyro(),
        trigger_engine=FakeTrigger(),
    )
    engine.add_event('error', r'Fallo en C:\\Users\\ExampleUser\\AppData\\Local\\Nikaido\\secret.log', severity='error')
    engine.start_capture(3)
    for index in range(12):
        connection.emit(state(index))
    capture = engine.stop_capture()
    assert len(capture) == 12
    assert capture[0]['source'] == 'raw_hid'
    assert capture[0]['buttons'] == ['cross']

    output = Path(engine.generate_report(str(tmp_path / 'report')))
    assert output.suffix == '.zip'
    with zipfile.ZipFile(output) as archive:
        assert {'report.json', 'capture.json', 'summary.txt', 'PRIVACY.txt'} <= set(archive.namelist())
        report_text = archive.read('report.json').decode('utf-8')
        assert 'ExampleUser' not in report_text
        assert 'secret.log' not in report_text or '<RUTA_USUARIO>' in report_text
        report = json.loads(report_text)
        assert report['snapshot']['profile'] == 'test_profile'
        assert report['snapshot']['health'] == 'excellent'
        privacy = archive.read('PRIVACY.txt').decode('utf-8')
        assert 'contenido de macros' in privacy
        payload = archive.read('capture.json').decode('utf-8')
        assert 'test_profile' not in payload


def test_capture_duration_is_bounded():
    engine = DiagnosticEngine()
    assert engine.start_capture(1) == 3.0
    assert engine.start_capture(99) == 30.0
