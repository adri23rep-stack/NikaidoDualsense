from tests.gui_source_catalog import GUI_SOURCE as TEXT


def test_calibration_page_is_registered():
    assert 'class CalibrationPage(ScrollPage)' in TEXT
    assert '"calibration": ("calibration_page", "gui.pages.input", "CalibrationPage")' in TEXT
    assert 'Drift, gyro y gatillos' in TEXT


def test_visual_response_curve_is_connected_to_input_studio():
    assert 'class ResponseCurveEditor(QWidget)' in TEXT
    assert 'self.curve_editor = ResponseCurveEditor(editable=True)' in TEXT
    assert 'custom_curve=self.curve_editor.get_points()' in TEXT


def test_calibration_reuses_existing_engines():
    assert 'engine.begin_drift_calibration(profile,stick,120)' in TEXT
    assert 'self.window.gyro_engine.begin_calibration()' in TEXT
