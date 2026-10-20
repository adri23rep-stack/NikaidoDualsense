import sys

from src import hid_backend


class FakeDevice:
    def __init__(self):
        self.opened = None
        self.nonblocking = []
        self.closed = False
        self.writes = []

    def open(self, vendor_id, product_id, serial_number=None):
        self.opened = (vendor_id, product_id, serial_number)

    def open_path(self, path):
        self.opened = ("path", path)

    def set_nonblocking(self, value):
        self.nonblocking.append(value)

    def read(self, length, timeout_ms=0):
        return [1, 2, 3][:length]

    def write(self, data):
        self.writes.append(bytes(data))
        return len(data)

    def close(self):
        self.closed = True

    def get_manufacturer_string(self):
        return "Sony"

    def get_product_string(self):
        return "DualSense Wireless Controller"

    def get_serial_number_string(self):
        return "ABC"

    def get_indexed_string(self, index):
        return str(index)

    def send_feature_report(self, data):
        return len(data)

    def get_feature_report(self, report_id, length):
        return [report_id] + [0] * (length - 1)


class FakeHID:
    __version__ = "test"

    def __init__(self):
        self.instances = []

    def device(self):
        instance = FakeDevice()
        self.instances.append(instance)
        return instance

    @staticmethod
    def enumerate(vendor_id=0, product_id=0):
        return [{
            "path": b"hid#dualsense",
            "vendor_id": vendor_id or 0x054C,
            "product_id": product_id or 0x0CE6,
            "serial_number": "ABC",
            "manufacturer_string": "Sony",
            "product_string": "DualSense Wireless Controller",
            "usage_page": 1,
            "usage": 5,
            "interface_number": 0,
        }]


def test_cython_hid_adapter_matches_pydualsense_api():
    fake = FakeHID()
    previous = sys.modules.pop("hidapi", None)
    try:
        module = hid_backend._install_cython_compat(fake)
        rows = module.enumerate(0x054C, 0)
        assert rows[0].vendor_id == 0x054C
        assert rows[0].product_id == 0x0CE6
        assert rows[0].path == b"hid#dualsense"

        device = module.Device(vendor_id=0x054C, product_id=0x0CE6)
        assert fake.instances[-1].opened == (0x054C, 0x0CE6, None)
        assert device.read(3) == [1, 2, 3]
        assert device.write(bytes([2, 3])) == 2
        assert device.get_manufacturer_string() == "Sony"
        device.close()
        assert fake.instances[-1].closed is True
    finally:
        sys.modules.pop("hidapi", None)
        if previous is not None:
            sys.modules["hidapi"] = previous
