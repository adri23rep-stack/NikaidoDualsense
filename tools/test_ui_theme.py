"""Pruebas del formato, empaquetado y seguridad de Nikaido UI Studio.

Se ejecutan sin control conectado y sin abrir ventanas:
    python -m unittest tools.test_ui_theme -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Optional

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from gui.ui_theme import (  # noqa: E402
    SCHEMA_VERSION,
    ThemeError,
    UIElement,
    UILayout,
    condition_matches,
    export_theme_package,
    install_theme,
    load_layout,
    save_layout,
    substitute_variables,
    validate_layout,
)


class UIThemeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_context = tempfile.TemporaryDirectory(prefix="nikaido_ui_test_")
        self.temp = Path(self.temp_context.name)

    def tearDown(self) -> None:
        self.temp_context.cleanup()

    def make_image(self, name: str, color=(90, 80, 220, 255)) -> Path:
        path = self.temp / name
        Image.new("RGBA", (32, 24), color).save(path)
        return path

    def make_layout(self, image_path: Optional[Path] = None) -> UILayout:
        elements = [
            UIElement(
                id="title",
                type="text",
                x=20,
                y=20,
                width=300,
                height=50,
                text="Batería {battery_percent}",
                font_size=20,
                page="main",
            ),
            UIElement(
                id="open_tools",
                type="button",
                x=20,
                y=90,
                width=180,
                height=54,
                text="Herramientas",
                action="page.open",
                action_args={"page": "tools"},
                page="main",
            ),
            UIElement(
                id="back",
                type="button",
                x=20,
                y=90,
                width=180,
                height=54,
                text="Volver",
                action="page.back",
                page="tools",
            ),
            UIElement(
                id="battery_bar",
                type="progress",
                x=20,
                y=165,
                width=220,
                height=24,
                text="{battery_percent}",
                page="*",
                metadata={
                    "value_variable": "battery",
                    "minimum": 0,
                    "maximum": 100,
                    "track_fill": "#242733",
                    "direction": "horizontal",
                },
            ),
            UIElement(
                id="bubble",
                type="speech_bubble",
                x=260,
                y=150,
                width=260,
                height=120,
                text="Perfil {active_profile}",
                page="main",
                metadata={"tail_position": "left", "tail_width": 30, "tail_height": 18},
            ),
        ]
        if image_path is not None:
            hover = self.make_image("hover.png", (120, 110, 250, 255))
            pressed = self.make_image("pressed.png", (50, 40, 170, 255))
            elements.append(
                UIElement(
                    id="art",
                    type="image",
                    x=400,
                    y=20,
                    width=128,
                    height=96,
                    source=image_path.name,
                    page="*",
                    metadata={
                        "fit": "contain",
                        "hover_source": hover.name,
                        "pressed_source": pressed.name,
                    },
                )
            )
        return UILayout(
            name="test_theme",
            canvas={"width": 900, "height": 560, "background": "#101116", "scale_mode": "contain"},
            pages=[{"id": "main", "name": "Inicio"}, {"id": "tools", "name": "Herramientas"}],
            default_page="main",
            elements=elements,
            base_dir=self.temp,
        )

    def test_valid_layout(self) -> None:
        layout = self.make_layout()
        errors, warnings = validate_layout(layout)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_page_target_validation(self) -> None:
        layout = self.make_layout()
        layout.elements[1].action_args["page"] = "missing"
        errors, _ = validate_layout(layout)
        self.assertTrue(any("pantalla inexistente" in error for error in errors))

    def test_progress_limits_are_validated(self) -> None:
        layout = self.make_layout()
        progress = next(element for element in layout.elements if element.type == "progress")
        progress.metadata["maximum"] = 0
        errors, _ = validate_layout(layout)
        self.assertTrue(any("máximo de progreso" in error for error in errors))

    def test_migrates_legacy_layout(self) -> None:
        legacy = {
            "schema_version": 1,
            "name": "legacy",
            "canvas": {"width": 900, "height": 560, "background": "#111111"},
            "elements": [
                {"id": "old", "type": "rectangle", "x": 0, "y": 0, "width": 100, "height": 60}
            ],
        }
        path = self.temp / "legacy.json"
        path.write_text(json.dumps(legacy), encoding="utf-8")
        layout = load_layout(path)
        self.assertEqual(layout.schema_version, SCHEMA_VERSION)
        self.assertEqual(layout.default_page, "main")
        self.assertEqual(layout.elements[0].page, "main")
        self.assertEqual(layout.canvas["scale_mode"], "contain")

    def test_json_roundtrip(self) -> None:
        layout = self.make_layout()
        path = save_layout(layout, self.temp / "theme.nikaido-ui.json")
        loaded = load_layout(path)
        self.assertEqual(loaded.name, layout.name)
        self.assertEqual(len(loaded.elements), len(layout.elements))
        self.assertEqual(loaded.pages, layout.pages)

    def test_portable_package_contains_all_image_states(self) -> None:
        source = self.make_image("normal.png")
        layout = self.make_layout(source)
        package = export_theme_package(layout, self.temp / "portable.nikaido-theme")

        with zipfile.ZipFile(package) as archive:
            names = set(archive.namelist())
            self.assertIn("manifest.json", names)
            self.assertEqual(len([name for name in names if name.startswith("assets/")]), 3)

        loaded = load_layout(package, extract_dir=self.temp / "extracted")
        errors, warnings = validate_layout(loaded, check_assets=True)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        image = next(element for element in loaded.elements if element.id == "art")
        self.assertTrue(loaded.resolve_asset(image.source).is_file())
        self.assertTrue(loaded.resolve_asset(image.metadata["hover_source"]).is_file())
        self.assertTrue(loaded.resolve_asset(image.metadata["pressed_source"]).is_file())

    def test_install_json_copies_assets(self) -> None:
        source = self.make_image("normal.png")
        layout = self.make_layout(source)
        json_path = save_layout(layout, self.temp / "source.json")
        installed = install_theme(json_path, self.temp / "themes")
        self.assertTrue(installed.source_path.is_file())
        image = next(element for element in installed.elements if element.id == "art")
        self.assertTrue(installed.resolve_asset(image.source).is_file())
        self.assertNotEqual(installed.resolve_asset(image.source), source)

    def test_zip_slip_is_blocked(self) -> None:
        package = self.temp / "evil.nikaido-theme"
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("../outside.txt", "nope")
            archive.writestr("manifest.json", "{}")
        with self.assertRaises(ThemeError):
            load_layout(package, extract_dir=self.temp / "install")
        self.assertFalse((self.temp / "outside.txt").exists())

    def test_conditions_are_safe_and_predictable(self) -> None:
        context = {
            "connected": True,
            "battery": 12,
            "is_charging": False,
            "active_profile_id": "sniper",
            "connection_type": "USB",
        }
        self.assertTrue(condition_matches("controller.connected", context))
        self.assertFalse(condition_matches("controller.disconnected", context))
        self.assertTrue(condition_matches("battery.low", context))
        self.assertTrue(condition_matches("profile:sniper", context))
        self.assertTrue(condition_matches("connection:usb", context))
        self.assertTrue(condition_matches("not:battery.charging", context))
        self.assertFalse(condition_matches("__import__('os')", context))

    def test_variable_substitution_preserves_unknown_tokens(self) -> None:
        result = substitute_variables(
            "{connection} · {battery_percent} · {unknown}",
            {"connection": "Conectado", "battery_percent": "88%"},
        )
        self.assertEqual(result, "Conectado · 88% · {unknown}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
