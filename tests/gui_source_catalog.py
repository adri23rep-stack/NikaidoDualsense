"""Índice de fuentes Qt para pruebas que no importan PySide6.

Las pantallas viven en módulos separados desde Nikaido 2.6. Las pruebas de
regresión siguen inspeccionando el código sin exigir un escritorio gráfico.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, Tuple

ROOT = Path(__file__).resolve().parents[1]
GUI_FILES = [
    ROOT / "gui" / "components.py",
    ROOT / "gui" / "curve_editor.py",
    ROOT / "gui" / "main_window.py",
    ROOT / "gui" / "low_profile_runtime.py",
    ROOT / "gui" / "profile_editor.py",
    ROOT / "gui" / "profile_gallery.py",
    ROOT / "gui" / "profile_visuals.py",
    *sorted((ROOT / "gui" / "pages").glob("*.py")),
]
SOURCES = {path: path.read_text(encoding="utf-8") for path in GUI_FILES}
GUI_SOURCE = "\n\n".join(SOURCES.values())

CLASS_INDEX: Dict[str, Tuple[Path, str, ast.ClassDef]] = {}
for path, source in SOURCES.items():
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            CLASS_INDEX[node.name] = (path, source, node)


def classes() -> Dict[str, ast.ClassDef]:
    return {name: data[2] for name, data in CLASS_INDEX.items()}


def class_source(name: str) -> str:
    _path, source, node = CLASS_INDEX[name]
    return ast.get_source_segment(source, node) or ""


def methods(name: str) -> set[str]:
    node = CLASS_INDEX[name][2]
    return {
        child.name
        for child in node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
