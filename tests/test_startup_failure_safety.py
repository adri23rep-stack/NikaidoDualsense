from pathlib import Path


def test_noconsole_gui_failure_never_falls_into_invisible_input_loop():
    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    assert 'interactive_console = bool(' in source
    assert 'not getattr(sys, "frozen", False)' in source
    assert 'self._run_console_mode()' in source
    assert 'self.shutdown()' in source
    assert 'Un ejecutable --noconsole no puede pedir comandos por input()' in source


def test_partial_initialization_is_cleaned_up_once():
    source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    assert 'self._shutdown_started = False' in source
    assert 'if self._shutdown_started:' in source
    assert 'raise RuntimeError("Nikaido no pudo inicializar sus módulos")' in source
