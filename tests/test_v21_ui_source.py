from pathlib import Path

from tests.gui_source_catalog import GUI_SOURCE

SOURCE = GUI_SOURCE
MAIN = (Path(__file__).resolve().parents[1] / 'main.py').read_text(encoding='utf-8')


def test_diagnostic_center_is_integrated():
    assert 'class MonitorPage' in SOURCE
    assert 'Centro de diagnóstico' in SOURCE
    assert 'Generar reporte' in SOURCE
    assert 'capture_progress' in SOURCE
    assert 'diagnostic_engine=self.diagnostic_engine' in MAIN


def test_advanced_mapper_editor_is_visible():
    assert 'class AdvancedBindingDialog' in SOURCE
    assert 'Capas y gestos' in SOURCE
    assert 'Pulsación larga' in SOURCE
    assert 'Cambiar capa' in SOURCE
    assert 'advanced_mapping_config' in SOURCE


def test_flick_stick_has_professional_controls():
    assert 'Flick Stick' in SOURCE
    assert 'flick_threshold' in SOURCE
    assert 'flick_pixels_per_degree' in SOURCE
    assert 'flick_turn_180_ms' in SOURCE
    assert 'Botón activador' in SOURCE
