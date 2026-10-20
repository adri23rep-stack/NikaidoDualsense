from tests.gui_source_catalog import GUI_SOURCE as SOURCE, class_source, classes, methods


def _classes():
    return classes()


def _methods(class_name):
    return methods(class_name)


def test_emulation_is_a_dedicated_page_and_navigation_item():
    assert "EmulationPage" in _classes()
    assert '"emulation": ("emulation_page", "gui.pages.system", "EmulationPage")' in SOURCE
    assert '("emulation", "◆", "Emulación", "DualSense, teclado y mouse")' in SOURCE
    assert '"emulation": ("Emulación"' in SOURCE


def test_emulation_page_contains_touchpad_mouse_and_sensitivity():
    methods = _methods("EmulationPage")
    assert "set_touchpad_enabled" in methods
    assert "set_touchpad_sensitivity" in methods
    assert '"Usar touchpad como mouse"' in SOURCE
    assert '"Sensibilidad", 0.5, 8.0' in SOURCE
    assert '"touchpad_mouse.enabled"' in SOURCE
    assert '"touchpad_mouse.sensitivity"' in SOURCE


def test_emulation_page_has_direct_gyro_switch():
    methods = _methods("EmulationPage")
    assert "set_gyro_enabled" in methods
    assert 'QCheckBox("Activar giroscopio")' in SOURCE
    assert 'changes["mode"] = "mouse"' in SOURCE
    assert 'lambda: self.window.navigate("gyro")' in SOURCE


def test_tools_no_longer_owns_emulation_actions():
    tools_source = class_source("ToolsPage")
    assert "Emulación Xbox" not in tools_source
    assert "Emulación DS4" not in tools_source
    assert "Desactivar emulación" not in tools_source


def test_mouse_to_virtual_gyro_is_optional_and_does_not_recreate_active_ds4():
    gyro_methods = _methods("GyroPage")
    emulation_methods = _methods("EmulationPage")
    assert "_refresh_mode_controls" in gyro_methods
    assert "set_mouse_gyro_enabled" in emulation_methods
    assert 'QCheckBox("Mouse → giroscopio virtual")' in SOURCE
    assert 'needs_ps4 = self._current_mode() != "ps4"' in SOURCE
    assert 'mouse_to_gyro_enabled=True' in SOURCE
