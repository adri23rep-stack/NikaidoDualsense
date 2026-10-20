from tests.gui_source_catalog import GUI_SOURCE as SOURCE, class_source, classes, methods

CLASSES = classes()


def methods_for(name):
    return methods(name)


def test_25_pages_are_lazy_and_visible_in_navigation():
    assert "AutoProfilesPage" in CLASSES
    assert "CompatibilityPage" in CLASSES
    assert '"automation": ("automation_page", "gui.pages.system", "AutoProfilesPage")' in SOURCE
    assert '"compatibility": ("compatibility_page", "gui.pages.system", "CompatibilityPage")' in SOURCE
    assert '("automation", "◫", "Perfiles automáticos"' in SOURCE
    assert '("compatibility", "◇", "Compatibilidad"' in SOURCE


def test_auto_profile_editor_supports_priority_delays_and_restore_status():
    page_methods = methods_for("AutoProfilesPage")
    assert {"save_rule", "edit_selected", "remove_selected", "refresh_status"} <= page_methods
    assert 'QCheckBox("Solo cuando el juego esté al frente")' in SOURCE
    assert 'self.enter_delay.setRange(0, 10000)' in SOURCE
    assert 'self.exit_delay.setRange(0, 10000)' in SOURCE
    assert 'Perfil de regreso' in SOURCE


def test_vibration_page_controls_game_feedback_bridge():
    page_methods = methods_for("VibrationPage")
    assert {"refresh_feedback", "save_feedback", "refresh_feedback_status"} <= page_methods
    assert 'QCheckBox("Devolver vibración al DualSense")' in SOURCE
    assert '"virtual_feedback"' in SOURCE
    assert 'feedback_registered' in SOURCE


def test_compatibility_page_requires_exact_user_selected_device():
    page_methods = methods_for("CompatibilityPage")
    assert {"refresh", "whitelist_nikaido", "toggle_cloak", "set_hidden"} <= page_methods
    assert "nunca oculta un dispositivo sin que tú lo elijas" in SOURCE
    assert 'QMessageBox.question' in class_source("CompatibilityPage")
