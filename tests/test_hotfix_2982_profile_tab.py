from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE_FILES = (
    ROOT / "gui" / "pages" / "profiles.py",
    ROOT / "gui" / "profile_gallery.py",
    ROOT / "gui" / "profile_editor.py",
    ROOT / "gui" / "profile_visuals.py",
)


def _literal_palette_keys() -> set[str]:
    tree = ast.parse((ROOT / "gui" / "design_system.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "C" for target in node.targets):
                value = ast.literal_eval(node.value)
                return set(value)
    raise AssertionError("No se encontró la paleta C")


def test_profile_studio_only_uses_existing_palette_keys():
    source = "\n".join(path.read_text(encoding="utf-8") for path in PROFILE_FILES)
    used = set(re.findall(r"C\[[\'\"]([^\'\"]+)[\'\"]\]", source))
    missing = used - _literal_palette_keys()
    assert not missing, f"Claves visuales inexistentes en Profile Studio: {sorted(missing)}"


def test_profile_studio_never_uses_the_removed_violet_palette_key():
    source = "\n".join(path.read_text(encoding="utf-8") for path in PROFILE_FILES)
    assert 'C["violet"]' not in source
    assert "C.get(\"accent2\", C[\"accent\"])" in source
