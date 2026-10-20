from tests.gui_source_catalog import GUI_SOURCE as SOURCE, classes, methods


def _classes():
    return classes()


def _method_names(class_name):
    return methods(class_name)


def test_macro_editor_has_visual_stick_and_per_action_timing():
    classes = _classes()
    assert "MacroStickPad" in classes
    assert "MacroStepDialog" in classes
    assert "Esperar después" in SOURCE
    assert '["#", "Tipo", "Acción", "Duración", "Después"]' in SOURCE


def test_macro_editor_supports_all_requested_triggers_and_profiles():
    assert "Presión de L2 o R2" in SOURCE
    assert "Combo de botones" in SOURCE
    assert "Dirección de palanca" in SOURCE
    assert "Repetir mientras se mantenga" in SOURCE
    methods = _method_names("MacroEditorDialog")
    assert {"select_current_profile", "select_all_profiles", "clear_profiles"} <= methods


def test_macro_library_has_polish_tools():
    methods = _method_names("MacrosPage")
    assert {
        "new_from_template",
        "toggle_selected",
        "import_macros",
        "export_selected",
        "duplicate_selected",
    } <= methods
    editor_methods = _method_names("MacroEditorDialog")
    assert {"duplicate_step", "set_uniform_delay", "test_steps", "toggle_recording"} <= editor_methods
    assert "Incluir palancas y gatillos" in SOURCE


def test_macro_recording_is_visible_while_capture_is_active():
    assert "get_recording_steps" in SOURCE
    assert "acciones capturadas" in SOURCE
    assert "self.steps_table.scrollToBottom()" in SOURCE
