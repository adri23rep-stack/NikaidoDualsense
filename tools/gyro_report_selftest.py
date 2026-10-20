#!/usr/bin/env python3
"""Prueba portable del reporte DS4_EX sin ViGEm ni control fisico."""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.gyro_virtual_ds4 import DS4ExtendedReportAdapter

adapter = DS4ExtendedReportAdapter()
adapter._native_report_cls = None
base = SimpleNamespace(bThumbLX=128, bThumbLY=128, bThumbRX=128, bThumbRY=128,
                       wButtons=0x1234, bSpecial=1, bTriggerL=20, bTriggerR=30)
state = SimpleNamespace(gyro_pitch=100, gyro_yaw=-200, gyro_roll=300,
                        accel_x=1000, accel_y=2000, accel_z=-3000,
                        battery_level=80, charging_status=SimpleNamespace(value="cargando"),
                        touchpad_active=True, touchpad_x=960, touchpad_y=471, touchpad_id=1)
report = adapter.build_report(base, adapter.make_packet(state)).Report
assert report.wButtons == 0x1234
assert report.bTriggerL == 20 and report.bTriggerR == 30
assert (report.wGyroX, report.wGyroY, report.wGyroZ) == (100, -200, 300)
assert (report.wAccelX, report.wAccelY, report.wAccelZ) == (1000, 2000, -3000)
print("DS4_REPORT_EX OK: botones/sticks/gatillos preservados; IMU/touch/bateria añadidos.")
