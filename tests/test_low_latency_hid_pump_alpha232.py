from types import SimpleNamespace
import threading
import time

from src.connection_manager import ConnectionManager


class FakeDevice:
    def __init__(self, owner, reports):
        self.owner = owner
        self.reports = list(reports)
        self.writes = []

    def read(self, _length):
        if not self.reports:
            self.owner.ds_thread = False
            return []
        report = self.reports.pop(0)
        if not self.reports:
            self.owner.ds_thread = False
        return report

    def write(self, data):
        self.writes.append(bytes(data))
        return len(data)


class FakeController:
    def __init__(self, reports, *, connection="USB"):
        self.ds_thread = True
        self.connected = True
        self.input_report_length = len(reports[0])
        self.conType = SimpleNamespace(name=connection)
        self.states = None
        self.device = FakeDevice(self, reports)
        self.read_input_calls = 0
        self.prepare_calls = 0

    def sendReport(self):
        raise AssertionError("La bomba original no debe ejecutarse")

    def readInput(self, _report):
        self.read_input_calls += 1

    def prepareReport(self):
        self.prepare_calls += 1
        return [0x02, 0xFF, 0x57, 0, 0] + [0] * 59

    def writeReport(self, report):
        return self.device.write(report)


def _usb_report(sequence):
    report = [0] * 64
    report[0] = 0x01
    report[1] = 128 + sequence
    report[7] = sequence
    report[8] = 0x08
    report[53] = 0x05
    return report


def _bt_report(sequence):
    # pydualsense elimina el byte BT inicial para que el mapa coincida con USB.
    return [0x31] + _usb_report(sequence) + [0] * 13


def test_pump_publishes_latest_raw_report_without_pydualsense_deep_decode():
    controller = FakeController([_usb_report(i) for i in range(1, 7)])
    manager = ConnectionManager()

    assert manager._install_low_latency_input_pump(controller) is True
    controller.sendReport()

    assert tuple(controller.states) == tuple(_usb_report(6))
    assert controller.read_input_calls == 0
    assert controller._nikaido_input_reports == 6
    # El bucle anterior escribía seis veces. La nueva bomba agrupa las salidas.
    assert controller._nikaido_output_writes == 1
    assert len(controller.device.writes) == 1
    assert controller._nikaido_output_skips >= 0
    assert controller._nikaido_pump_active is False
    assert controller._nikaido_output_thread_active is False



class BlockingOutputDevice(FakeDevice):
    def __init__(self, owner, reports):
        super().__init__(owner, reports)
        self.write_started = threading.Event()
        self.read_times = []

    def read(self, length):
        # Obliga a que la escritura física ya esté bloqueada antes de leer.
        self.write_started.wait(0.2)
        self.read_times.append(time.perf_counter())
        return super().read(length)

    def write(self, data):
        self.write_started.set()
        time.sleep(0.05)
        return super().write(data)


def test_slow_physical_output_does_not_block_input_reads():
    reports = [_usb_report(i) for i in range(1, 7)]
    controller = FakeController(reports)
    controller.device = BlockingOutputDevice(controller, reports)
    manager = ConnectionManager()

    manager._install_low_latency_input_pump(controller)
    controller.sendReport()

    assert controller._nikaido_input_reports == 6
    assert controller.device.write_started.is_set()
    # La escritura tarda 50 ms, pero las seis lecturas deben avanzar en paralelo.
    assert controller.device.read_times[-1] - controller.device.read_times[0] < 0.02


def test_pump_normalizes_bluetooth_prefix_before_publishing():
    controller = FakeController([_bt_report(9)], connection="BT")
    manager = ConnectionManager()

    manager._install_low_latency_input_pump(controller)
    controller.sendReport()

    assert tuple(controller.states) == tuple(_usb_report(9) + [0] * 13)
    assert controller.states[7] == 9
    assert len(controller.states) == 77


def test_diagnostics_expose_pump_status_and_output_rate_limit():
    manager = ConnectionManager()
    controller = SimpleNamespace(
        _nikaido_low_latency_pump=True,
        _nikaido_pump_active=True,
        _nikaido_output_thread_active=True,
        _nikaido_input_reports=123,
        _nikaido_output_writes=7,
        _nikaido_output_skips=116,
        _nikaido_pump_error="",
    )
    manager.dualsense = controller

    pump = manager.get_diagnostics_snapshot()["hid_input_pump"]

    assert pump["installed"] is True
    assert pump["active"] is True
    assert pump["output_thread_active"] is True
    assert pump["input_reports"] == 123
    assert pump["physical_output_writes"] == 7
    assert pump["physical_output_skips"] == 116
    assert pump["physical_output_limit_hz"] == 60.0
