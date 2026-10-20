"""Regresiones del pulido de primer inicio de Nikaido 2.9.3."""

from pathlib import Path

from src.connection_manager import ConnectionManager, ControllerState

ROOT = Path(__file__).resolve().parents[1]


def test_battery_starts_unknown_instead_of_fake_zero():
    state = ControllerState(connected=True)
    assert state.battery_level == 0
    assert state.battery_valid is False

    manager = ConnectionManager()
    manager._connected = True
    values = []
    manager.on_battery_change(lambda level, status: values.append((level, status)))
    assert values == []


def test_dashboard_uses_stable_battery_meter_and_unknown_copy():
    source = (ROOT / "gui" / "pages" / "dashboard.py").read_text(encoding="utf-8")
    assert "def _battery_stat" in source
    assert "self.battery_bar = QProgressBar()" in source
    assert "stats.addWidget(self.battery_box, 0, 0, 1, 2)" in source
    assert 'self.battery_value = QLabel("—")' in source
    assert 'tr("Leyendo batería…" if connected else "Sin control conectado"' in source
    assert '"0%", C["green"]' not in source


def test_first_run_language_is_large_and_cannot_be_skipped():
    source = (ROOT / "gui" / "pages" / "settings.py").read_text(encoding="utf-8")
    assert "def _build_language_page" in source
    assert 'choice.setProperty("languageChoice", True)' in source
    assert 'choice.setProperty("i18nSkipText", True)' in source
    assert "self._requires_language_choice" in source
    assert "self.skip_button.setVisible(self._index > self.LANGUAGE_STEP)" in source
    assert "if self._index == self.LANGUAGE_STEP and not self._language_confirmed" in source
    assert 'pm.set_setting("onboarding.language_confirmed", True)' in source


def test_history_files_no_longer_hide_the_root_batch_files():
    forbidden = ("HOTFIX_*.md", "RELEASE_*.md", "REPORTE_*.md", "VALIDACION*.txt", "CAMBIOS_*.md")
    assert all(not list(ROOT.glob(pattern)) for pattern in forbidden)
    assert (ROOT / "docs" / "history" / "README.md").is_file()
    for name in ("COMPILAR_NIKAIDO.bat", "COMPILAR_NIKAIDO_PROTEGIDO.bat", "CREAR_INSTALADOR_PROTEGIDO.bat"):
        assert (ROOT / name).is_file()


def test_visible_licenses_put_owner_name_only_on_last_line():
    for name in ("LICENSE", "EULA_ES.txt", "EULA_EN.txt", "EULA_PT_BR.txt", "EULA_NIKAIDO.txt"):
        lines = (ROOT / name).read_text(encoding="utf-8").strip().splitlines()
        assert lines[-1] == "© Team Nikaido"
        assert all("Team Nikaido" not in line for line in lines[:-1])
