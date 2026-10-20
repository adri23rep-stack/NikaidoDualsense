"""Modelo, validación y empaquetado de interfaces personalizadas de Nikaido.

El módulo no depende de Tkinter. Esto permite validar y migrar temas incluso en
modo consola, durante pruebas o antes de construir la interfaz gráfica.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image, UnidentifiedImageError

from nikaido_version import APP_VERSION
from src.security_utils import (
    SecurityValidationError,
    is_within_directory,
    read_json_file_limited,
    validate_json_complexity,
    validate_zip_member_name,
)

SCHEMA_VERSION = 3
THEME_EXTENSION = ".nikaido-theme"

ELEMENT_TYPES = ("rectangle", "ellipse", "text", "speech_bubble", "button", "progress", "image", "hotspot")

ACTION_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "none": {"label": "Sin acción"},
    "page.open": {"label": "Abrir pantalla personalizada", "args": {"page": "main"}},
    "page.back": {"label": "Volver a la pantalla anterior"},
    "navigate.profiles": {"label": "Abrir Perfiles"},
    "navigate.buttons": {"label": "Abrir Botones"},
    "navigate.triggers": {"label": "Abrir Gatillos"},
    "navigate.macros": {"label": "Abrir Macros"},
    "navigate.input_studio": {"label": "Abrir Nikaido Input Studio"},
    "navigate.settings": {"label": "Abrir Configuración"},
    "controller.connect": {"label": "Intentar conectar control"},
    "controller.disconnect": {"label": "Desconectar control"},
    "profile.apply": {"label": "Aplicar perfil", "args": {"profile_id": ""}},
    "profile.next": {"label": "Aplicar perfil siguiente"},
    "profile.previous": {"label": "Aplicar perfil anterior"},
    "profile.import": {"label": "Importar perfil"},
    "profile.export": {"label": "Exportar perfil activo"},
    "trigger.reset": {"label": "Restablecer gatillos"},
    "macro.new": {"label": "Crear macro"},
    "macro.play": {"label": "Reproducir macro", "args": {"macro_id": ""}},
    "macro.toggle": {"label": "Activar o desactivar macros"},
    "buttons.reset": {"label": "Restablecer botones"},
    "emulation.xbox": {"label": "Activar emulación Xbox 360"},
    "emulation.ps4": {"label": "Activar emulación PlayStation 4"},
    "emulation.off": {"label": "Apagar emulación"},
    "led.choose": {"label": "Elegir color LED"},
    "player.set": {"label": "Cambiar número de jugador", "args": {"player": 1}},
    "bluetooth.reset": {"label": "Reiniciar Bluetooth"},
    "ui.editor": {"label": "Abrir editor visual"},
    "ui.reload": {"label": "Recargar interfaz"},
    "ui.standard": {"label": "Mostrar interfaz clásica"},
    "ui.custom": {"label": "Mostrar interfaz personalizada"},
    "ui.disable": {"label": "Desactivar interfaz personalizada"},
    "window.fullscreen.toggle": {"label": "Alternar pantalla completa"},
    "app.minimize": {"label": "Minimizar aplicación"},
    "app.close": {"label": "Cerrar aplicación"},
}
DEFAULT_ACTIONS = tuple(ACTION_DEFINITIONS)

VARIABLES = {
    "app_version": APP_VERSION,
    "connection": "Desconectado",
    "connection_type": "",
    "battery": "--",
    "battery_percent": "--%",
    "charging": "No",
    "active_profile": "Ninguno",
    "active_profile_id": "",
    "profile_count": "0",
    "emulation_mode": "Apagado",
    "macros_enabled": "No",
    "status": "Listo",
    "l2": "0",
    "r2": "0",
    "time": "00:00",
    "date": "01/01/2000",
}

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?$")
_SAFE_ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
MAX_THEME_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_THEME_UNPACKED_BYTES = 100 * 1024 * 1024
MAX_THEME_MEMBER_BYTES = 25 * 1024 * 1024
MAX_THEME_MEMBERS = 256
MAX_THEME_JSON_BYTES = 2 * 1024 * 1024
MAX_THEME_COMPRESSION_RATIO = 250
MAX_THEME_ELEMENTS = 1_000
MAX_THEME_PAGES = 64
MAX_THEME_IMAGE_PIXELS = 20_000_000
MAX_THEME_IMAGE_FRAMES = 240
MAX_THEME_ANIMATION_PIXELS = 80_000_000


def _theme_asset_error(path: Path) -> str:
    """Devuelve un motivo legible si una imagen puede agotar recursos."""
    try:
        if not path.is_file():
            return "no existe"
        if path.suffix.lower() not in _SAFE_ASSET_EXTENSIONS:
            return f"formato no permitido ({path.suffix})"
        if path.stat().st_size > MAX_THEME_MEMBER_BYTES:
            return "supera 25 MB"
        with Image.open(path) as image:
            width, height = image.size
            frames = max(1, int(getattr(image, "n_frames", 1) or 1))
            pixels = int(width) * int(height)
            if width <= 0 or height <= 0 or pixels > MAX_THEME_IMAGE_PIXELS:
                return "dimensiones demasiado grandes"
            if frames > MAX_THEME_IMAGE_FRAMES:
                return f"supera {MAX_THEME_IMAGE_FRAMES} cuadros"
            if pixels * frames > MAX_THEME_ANIMATION_PIXELS:
                return "animación demasiado pesada"
            image.verify()
    except (OSError, ValueError, UnidentifiedImageError):
        return "archivo dañado o no reconocido"
    return ""


class ThemeError(ValueError):
    """Error legible asociado a un diseño o paquete de tema."""


@dataclass
class UIElement:
    id: str
    type: str
    x: float
    y: float
    width: float
    height: float
    opacity: float = 1.0
    rotation: float = 0.0
    z_index: int = 0
    page: str = "main"
    action: str = "none"
    action_args: Dict[str, Any] = field(default_factory=dict)
    visible: bool = True
    visible_when: str = "always"
    locked: bool = False
    text: str = ""
    font_family: str = "Segoe UI"
    font_size: int = 18
    font_weight: str = "normal"
    text_color: str = "#FFFFFF"
    text_align: str = "left"
    fill: str = "#7C6FF0"
    outline: str = ""
    outline_width: int = 0
    radius: int = 16
    source: str = ""
    tooltip: str = ""
    hover_fill: str = ""
    pressed_fill: str = ""
    cursor: str = "hand2"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "UIElement":
        if not isinstance(raw, dict):
            raise ThemeError("Cada elemento del tema debe ser un objeto JSON.")
        allowed = {f.name for f in fields(cls)}
        clean = {k: v for k, v in raw.items() if k in allowed}
        clean.setdefault("id", uuid.uuid4().hex[:10])
        clean.setdefault("type", "rectangle")
        clean.setdefault("x", 0)
        clean.setdefault("y", 0)
        clean.setdefault("width", 100)
        clean.setdefault("height", 60)
        clean.setdefault("action_args", {})
        clean.setdefault("metadata", {})
        for key in (
            "id", "type", "page", "action", "visible_when", "text",
            "font_family", "font_weight", "text_color", "text_align", "fill",
            "outline", "source", "tooltip", "hover_fill", "pressed_fill", "cursor",
        ):
            clean[key] = str(clean.get(key, ""))[:4096]
        for key, fallback in (
            ("x", 0.0), ("y", 0.0), ("width", 100.0), ("height", 60.0),
            ("opacity", 1.0), ("rotation", 0.0),
        ):
            try:
                clean[key] = float(clean.get(key, fallback))
            except (TypeError, ValueError, OverflowError):
                clean[key] = fallback
        for key, fallback in (
            ("z_index", 0), ("font_size", 18), ("outline_width", 0), ("radius", 16),
        ):
            try:
                clean[key] = int(clean.get(key, fallback))
            except (TypeError, ValueError, OverflowError):
                clean[key] = fallback
        for key in ("visible", "locked"):
            clean[key] = bool(clean.get(key, False if key == "locked" else True))
        if not isinstance(clean.get("action_args"), dict):
            clean["action_args"] = {}
        if not isinstance(clean.get("metadata"), dict):
            clean["metadata"] = {}
        return cls(**clean)


@dataclass
class UILayout:
    name: str = "custom_layout"
    description: str = ""
    author: str = ""
    schema_version: int = SCHEMA_VERSION
    canvas: Dict[str, Any] = field(default_factory=lambda: {
        "width": 900,
        "height": 560,
        "background": "#17171C",
        "scale_mode": "contain",
    })
    pages: List[Dict[str, str]] = field(default_factory=lambda: [{"id": "main", "name": "Inicio"}])
    default_page: str = "main"
    elements: List[UIElement] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    base_dir: Optional[Path] = field(default=None, repr=False, compare=False)
    source_path: Optional[Path] = field(default=None, repr=False, compare=False)
    allow_external_assets: bool = field(default=False, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "canvas": dict(self.canvas),
            "pages": [dict(page) for page in self.pages],
            "default_page": self.default_page,
            "actions": list(DEFAULT_ACTIONS),
            "elements": [asdict(element) for element in sorted(self.elements, key=lambda e: e.z_index)],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, base_dir: Optional[Path] = None,
                  source_path: Optional[Path] = None,
                  allow_external_assets: bool = False) -> "UILayout":
        validate_json_complexity(
            data,
            label="El tema",
            max_nodes=80_000,
            max_collection_items=10_000,
            max_string_length=65_536,
        )
        migrated = migrate_layout(data)
        raw_elements = migrated.get("elements", [])
        if not isinstance(raw_elements, list) or len(raw_elements) > MAX_THEME_ELEMENTS:
            raise ThemeError(f"El tema supera el límite de {MAX_THEME_ELEMENTS} elementos.")
        raw_pages = migrated.get("pages") or [{"id": "main", "name": "Inicio"}]
        if not isinstance(raw_pages, list) or len(raw_pages) > MAX_THEME_PAGES:
            raise ThemeError(f"El tema supera el límite de {MAX_THEME_PAGES} pantallas.")
        elements = [UIElement.from_dict(item) for item in raw_elements]
        return cls(
            name=str(migrated.get("name") or "custom_layout")[:120],
            description=str(migrated.get("description") or "")[:2_000],
            author=str(migrated.get("author") or "")[:120],
            schema_version=SCHEMA_VERSION,
            canvas=dict(migrated.get("canvas") or {}),
            pages=[dict(page) for page in raw_pages if isinstance(page, dict)],
            default_page=str(migrated.get("default_page") or "main"),
            elements=elements,
            metadata=dict(migrated.get("metadata") or {}),
            base_dir=Path(base_dir).resolve() if base_dir else None,
            source_path=Path(source_path).resolve() if source_path else None,
            allow_external_assets=bool(allow_external_assets),
        )

    def resolve_asset(self, source: str) -> Optional[Path]:
        if not source:
            return None
        raw = str(source).strip()
        if (
            raw.startswith(("\\\\", "//", "\\\\?\\", "\\\\.\\"))
            or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", raw)
        ):
            return None
        path = Path(os.path.expandvars(os.path.expanduser(raw)))
        if path.is_absolute():
            return path.resolve() if self.allow_external_assets else None
        if self.base_dir:
            resolved = (self.base_dir / path).resolve()
            return resolved if is_within_directory(resolved, self.base_dir) else None
        return path.resolve()


def migrate_layout(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migra diseños antiguos a la versión actual sin destruir campos conocidos."""
    if not isinstance(data, dict):
        raise ThemeError("El diseño debe ser un objeto JSON.")

    version = int(data.get("schema_version", 1) or 1)
    if version > SCHEMA_VERSION:
        raise ThemeError(
            f"El tema usa el esquema {version}, pero esta versión solo admite hasta {SCHEMA_VERSION}."
        )

    migrated = json.loads(json.dumps(data))  # copia profunda de tipos JSON
    if version <= 2:
        migrated.setdefault("description", "")
        migrated.setdefault("author", "")
        migrated.setdefault("metadata", {})
        migrated.setdefault("pages", [{"id": "main", "name": "Inicio"}])
        migrated.setdefault("default_page", "main")
        canvas = migrated.setdefault("canvas", {})
        canvas.setdefault("scale_mode", "contain")
        for raw in migrated.get("elements", []):
            raw.setdefault("page", "main")
            raw.setdefault("action_args", {})
            raw.setdefault("visible_when", "always")
            raw.setdefault("font_family", "Segoe UI")
            raw.setdefault("font_weight", "normal")
            raw.setdefault("text_align", "left")
            raw.setdefault("outline_width", 0)
            raw.setdefault("tooltip", "")
            raw.setdefault("hover_fill", "")
            raw.setdefault("pressed_fill", "")
            raw.setdefault("cursor", "hand2")
        migrated["schema_version"] = SCHEMA_VERSION
    return migrated


def _is_color(value: str, *, allow_empty: bool = True) -> bool:
    if not value:
        return allow_empty
    return bool(_HEX_RE.match(str(value)))


def _condition_is_supported(condition: str) -> bool:
    value = (condition or "always").strip().lower()
    if value.startswith("not:"):
        return _condition_is_supported(value[4:])
    if value in {
        "", "always", "true", "never", "false",
        "controller.connected", "controller.disconnected",
        "battery.charging", "battery.low",
    }:
        return True
    if value.startswith("profile:"):
        return bool(value.split(":", 1)[1])
    if value.startswith("connection:"):
        return value.split(":", 1)[1] in {"usb", "bluetooth"}
    return False


def validate_layout(layout: UILayout, *, check_assets: bool = True) -> Tuple[List[str], List[str]]:
    """Devuelve (errores, advertencias). No ejecuta ni evalúa contenido del tema."""
    errors: List[str] = []
    warnings: List[str] = []

    try:
        width = int(layout.canvas.get("width", 0))
        height = int(layout.canvas.get("height", 0))
    except (TypeError, ValueError, OverflowError):
        width = height = 0
    if width < 320 or height < 240:
        errors.append("El lienzo debe medir al menos 320 × 240.")
    if width > 7680 or height > 4320:
        errors.append("El lienzo supera el límite de 7680 × 4320.")
    if not _is_color(str(layout.canvas.get("background", "")), allow_empty=False):
        errors.append("El color de fondo del lienzo no es válido.")
    if layout.canvas.get("scale_mode", "contain") not in {"contain", "cover", "stretch"}:
        errors.append("scale_mode debe ser contain, cover o stretch.")

    page_ids: set[str] = set()
    for page in layout.pages:
        page_id = str(page.get("id", "")).strip()
        if not page_id or page_id in page_ids:
            errors.append("Las pantallas deben tener IDs únicos y no vacíos.")
            continue
        if not re.match(r"^[A-Za-z0-9_.-]+$", page_id):
            errors.append(f"ID de pantalla no válido: {page_id}")
        page_ids.add(page_id)
    if not page_ids:
        errors.append("El diseño debe contener al menos una pantalla.")
    if layout.default_page not in page_ids:
        errors.append("La pantalla predeterminada no existe.")

    seen: set[str] = set()
    for index, element in enumerate(layout.elements, start=1):
        prefix = f"Elemento {index} ({element.id})"
        if not element.id or element.id in seen:
            errors.append(f"{prefix}: ID vacío o duplicado.")
        seen.add(element.id)
        if element.type not in ELEMENT_TYPES:
            errors.append(f"{prefix}: tipo '{element.type}' no compatible.")
        if element.page not in page_ids and element.page != "*":
            errors.append(f"{prefix}: pantalla inexistente '{element.page}'.")
        if element.action == "page.open":
            target_page = str(element.action_args.get("page", ""))
            if target_page not in page_ids:
                errors.append(f"{prefix}: la acción page.open apunta a una pantalla inexistente.")
        if element.width <= 0 or element.height <= 0:
            errors.append(f"{prefix}: ancho y alto deben ser mayores que cero.")
        if not 0 <= element.opacity <= 1:
            errors.append(f"{prefix}: opacidad fuera del rango 0–1.")
        if element.action not in ACTION_DEFINITIONS:
            warnings.append(f"{prefix}: acción desconocida '{element.action}', se ignorará.")
        if not _condition_is_supported(element.visible_when):
            warnings.append(f"{prefix}: condición desconocida '{element.visible_when}', permanecerá oculto.")
        if element.action == "profile.apply" and not str(element.action_args.get("profile_id", "")).strip():
            warnings.append(f"{prefix}: profile.apply no tiene profile_id.")
        if element.action == "macro.play" and not str(element.action_args.get("macro_id", "")).strip():
            warnings.append(f"{prefix}: macro.play no tiene macro_id.")
        if element.action == "player.set":
            try:
                player = int(element.action_args.get("player", 1))
            except (TypeError, ValueError, OverflowError):
                player = 0
            if player not in {1, 2, 3, 4}:
                errors.append(f"{prefix}: player.set solo admite jugadores del 1 al 4.")
        for attr in ("text_color", "fill", "outline", "hover_fill", "pressed_fill"):
            if not _is_color(str(getattr(element, attr, ""))):
                errors.append(f"{prefix}: color inválido en {attr}.")
        if element.type == "image":
            if not element.source:
                errors.append(f"{prefix}: no tiene imagen asignada.")
            elif check_assets:
                asset = layout.resolve_asset(element.source)
                if not asset or not asset.is_file():
                    errors.append(f"{prefix}: no se encontró el recurso '{element.source}'.")
                else:
                    asset_error = _theme_asset_error(asset)
                    if asset_error:
                        errors.append(f"{prefix}: imagen rechazada: {asset_error}.")
            if check_assets:
                for state_key in ("hover_source", "pressed_source"):
                    state_source = str(element.metadata.get(state_key, "")).strip()
                    if not state_source:
                        continue
                    state_asset = layout.resolve_asset(state_source)
                    if not state_asset or not state_asset.is_file():
                        errors.append(f"{prefix}: no se encontró {state_key} '{state_source}'.")
                    else:
                        state_error = _theme_asset_error(state_asset)
                        if state_error:
                            errors.append(f"{prefix}: {state_key} rechazado: {state_error}.")
        if element.type in {"text", "speech_bubble", "button", "progress"} and element.font_size < 6:
            warnings.append(f"{prefix}: el texto podría ser ilegible por su tamaño.")
        if element.type == "progress":
            variable = str(element.metadata.get("value_variable", "battery")).strip()
            try:
                minimum = float(element.metadata.get("minimum", 0))
                maximum = float(element.metadata.get("maximum", 100))
            except (TypeError, ValueError, OverflowError):
                errors.append(f"{prefix}: límites de progreso inválidos.")
            else:
                if maximum <= minimum:
                    errors.append(f"{prefix}: el máximo de progreso debe superar al mínimo.")
            if not re.match(r"^[A-Za-z0-9_.-]+$", variable):
                errors.append(f"{prefix}: variable de progreso no válida.")
            track_fill = str(element.metadata.get("track_fill", "#242733"))
            if not _is_color(track_fill, allow_empty=False):
                errors.append(f"{prefix}: color de pista inválido.")
            if element.metadata.get("direction", "horizontal") not in {"horizontal", "vertical"}:
                errors.append(f"{prefix}: dirección de progreso inválida.")
        if element.x + element.width < 0 or element.y + element.height < 0 or element.x > width or element.y > height:
            warnings.append(f"{prefix}: está completamente fuera del lienzo.")

    return errors, warnings


def load_layout(
    path: Union[os.PathLike, str],
    *,
    extract_dir: Optional[Union[os.PathLike, str]] = None,
    allow_external_assets: bool = False,
) -> UILayout:
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise ThemeError(f"No se encontró el tema: {path}")
    if path.stat().st_size > MAX_THEME_ARCHIVE_BYTES:
        raise ThemeError("El tema supera el límite de 50 MB.")

    if path.suffix.lower() == ".zip" or path.name.lower().endswith(THEME_EXTENSION):
        persistent = extract_dir is not None
        target_root = (
            Path(extract_dir).resolve()
            if persistent
            else Path(tempfile.mkdtemp(prefix="nikaido_theme_"))
        )
        target_root.mkdir(parents=True, exist_ok=True)
        destination = target_root / f"{path.stem}_{hashlib.sha256(str(path).encode()).hexdigest()[:10]}"
        staging = (
            target_root / f".{destination.name}.{uuid.uuid4().hex}.tmp"
            if persistent
            else destination
        )
        staging.mkdir(parents=True)
        backup: Optional[Path] = None
        try:
            _safe_extract_zip(path, staging)
            manifest = staging / "manifest.json"
            if not manifest.is_file():
                candidates = list(staging.rglob("manifest.json"))
                if len(candidates) != 1:
                    raise ThemeError("El paquete no contiene un manifest.json válido.")
                manifest = candidates[0]
            try:
                data = read_json_file_limited(
                    manifest,
                    label="El manifest del tema",
                    max_bytes=MAX_THEME_JSON_BYTES,
                    max_nodes=80_000,
                    max_collection_items=10_000,
                )
            except SecurityValidationError as exc:
                raise ThemeError(str(exc)) from exc
            layout = UILayout.from_dict(
                data,
                base_dir=manifest.parent,
                source_path=path,
                allow_external_assets=False,
            )
            errors, _warnings = validate_layout(layout, check_assets=True)
            if errors:
                raise ThemeError("Tema inválido:\n- " + "\n- ".join(errors))

            if persistent:
                manifest_relative = manifest.relative_to(staging)
                if destination.exists() or destination.is_symlink():
                    backup = target_root / f".{destination.name}.{uuid.uuid4().hex}.bak"
                    os.replace(destination, backup)
                try:
                    os.replace(staging, destination)
                except Exception:
                    if backup is not None and backup.exists() and not destination.exists():
                        os.replace(backup, destination)
                    raise
                if backup is not None:
                    shutil.rmtree(backup, ignore_errors=True)
                manifest = destination / manifest_relative
                layout.base_dir = manifest.parent.resolve()
            return layout
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            if backup is not None and backup.exists() and not destination.exists():
                try:
                    os.replace(backup, destination)
                except OSError:
                    pass
            raise

    try:
        data = read_json_file_limited(
            path,
            label="El archivo de tema",
            max_bytes=MAX_THEME_JSON_BYTES,
            max_nodes=80_000,
            max_collection_items=10_000,
        )
    except SecurityValidationError as exc:
        raise ThemeError(str(exc)) from exc
    return UILayout.from_dict(
        data,
        base_dir=path.parent,
        source_path=path,
        allow_external_assets=allow_external_assets,
    )


def save_layout(layout: UILayout, path: Union[os.PathLike, str]) -> Path:
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(layout.to_dict(), ensure_ascii=False, indent=2) + "\n"
    temp = path.with_suffix(path.suffix + ".tmp")
    try:
        temp.write_text(payload, encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
    layout.source_path = path
    layout.base_dir = path.parent
    return path


def export_theme_package(layout: UILayout, destination: Union[os.PathLike, str]) -> Path:
    """Exporta un paquete ZIP portable con manifest y recursos deduplicados."""
    destination = Path(destination).expanduser().resolve()
    if not destination.name.lower().endswith(THEME_EXTENSION):
        destination = destination.with_name(destination.name + THEME_EXTENSION)
    destination.parent.mkdir(parents=True, exist_ok=True)

    errors, _ = validate_layout(layout, check_assets=True)
    if errors:
        raise ThemeError("No se puede exportar:\n- " + "\n- ".join(errors))

    manifest = layout.to_dict()
    asset_map: Dict[Path, str] = {}
    used_names: set[str] = set()

    for raw, element in zip(manifest["elements"], sorted(layout.elements, key=lambda e: e.z_index)):
        if element.type != "image" or not element.source:
            continue
        source = layout.resolve_asset(element.source)
        if not source or not source.is_file():
            continue
        if source not in asset_map:
            digest = hashlib.sha256(source.read_bytes()).hexdigest()[:10]
            stem = re.sub(r"[^A-Za-z0-9._-]+", "_", source.stem).strip("._") or "asset"
            name = f"{stem}_{digest}{source.suffix.lower()}"
            counter = 2
            while name.lower() in used_names:
                name = f"{stem}_{digest}_{counter}{source.suffix.lower()}"
                counter += 1
            used_names.add(name.lower())
            asset_map[source] = f"assets/{name}"
        raw["source"] = asset_map[source]

        metadata = raw.get("metadata", {})
        for key in ("hover_source", "pressed_source"):
            extra_source = metadata.get(key)
            if not extra_source:
                continue
            extra = layout.resolve_asset(str(extra_source))
            if extra and extra.is_file():
                if extra not in asset_map:
                    digest = hashlib.sha256(extra.read_bytes()).hexdigest()[:10]
                    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", extra.stem).strip("._") or "asset"
                    name = f"{stem}_{digest}{extra.suffix.lower()}"
                    used_names.add(name.lower())
                    asset_map[extra] = f"assets/{name}"
                metadata[key] = asset_map[extra]

    temp = destination.with_suffix(destination.suffix + ".tmp")
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for source, relative in asset_map.items():
                archive.write(source, relative)
        os.replace(temp, destination)
    finally:
        if temp.exists():
            temp.unlink(missing_ok=True)
    return destination


def install_theme(path: Union[os.PathLike, str], themes_dir: Union[os.PathLike, str]) -> UILayout:
    """Instala un JSON o paquete en un directorio persistente y devuelve el layout."""
    source = Path(path).expanduser().resolve()
    themes_dir = Path(themes_dir).expanduser().resolve()
    themes_dir.mkdir(parents=True, exist_ok=True)

    if source.name.lower().endswith(THEME_EXTENSION) or source.suffix.lower() == ".zip":
        layout = load_layout(source, extract_dir=themes_dir, allow_external_assets=False)
        errors, _ = validate_layout(layout, check_assets=True)
        if errors:
            raise ThemeError("Tema inválido:\n- " + "\n- ".join(errors))
        if layout.base_dir:
            manifest = layout.base_dir / "manifest.json"
            if manifest.is_file():
                layout.source_path = manifest
        return layout

    layout = load_layout(source, allow_external_assets=False)
    errors, _ = validate_layout(layout, check_assets=True)
    if errors:
        raise ThemeError("Tema inválido:\n- " + "\n- ".join(errors))

    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", layout.name).strip("._") or "theme"
    destination_dir = themes_dir / f"{slug}_{uuid.uuid4().hex[:8]}"
    assets_dir = destination_dir / "assets"
    destination_dir.mkdir(parents=True)
    assets_dir.mkdir()

    clone = UILayout.from_dict(layout.to_dict(), base_dir=destination_dir)
    clone.name = layout.name
    copied_assets: Dict[Path, Path] = {}

    def copy_asset(src: Path) -> Path:
        if src in copied_assets:
            return copied_assets[src]
        digest = hashlib.sha256(src.read_bytes()).hexdigest()[:10]
        dst = assets_dir / f"{src.stem}_{digest}{src.suffix.lower()}"
        shutil.copy2(src, dst)
        copied_assets[src] = dst
        return dst

    for cloned, original in zip(clone.elements, sorted(layout.elements, key=lambda e: e.z_index)):
        if original.type == "image" and original.source:
            src = layout.resolve_asset(original.source)
            if src and src.is_file():
                dst = copy_asset(src)
                cloned.source = str(Path("assets") / dst.name)
        for key in ("hover_source", "pressed_source"):
            extra_source = original.metadata.get(key)
            if not extra_source:
                continue
            src = layout.resolve_asset(str(extra_source))
            if src and src.is_file():
                dst = copy_asset(src)
                cloned.metadata[key] = str(Path("assets") / dst.name)
    manifest = save_layout(clone, destination_dir / "manifest.json")
    clone.source_path = manifest
    clone.base_dir = destination_dir
    return clone


def _safe_extract_zip(source: Path, destination: Path) -> None:
    """Extrae evitando Zip Slip y archivos descomprimidos absurdamente grandes."""
    total = 0
    with zipfile.ZipFile(source, "r") as archive:
        members = archive.infolist()
        if len(members) > MAX_THEME_MEMBERS:
            raise ThemeError(f"El paquete supera el límite de {MAX_THEME_MEMBERS} archivos.")
        seen: set[str] = set()
        for member in members:
            try:
                safe_name = validate_zip_member_name(member.filename, label="paquete de tema")
            except SecurityValidationError as exc:
                raise ThemeError(str(exc)) from exc
            key = safe_name.casefold()
            if key in seen:
                raise ThemeError("El paquete contiene nombres duplicados o ambiguos.")
            seen.add(key)
            if member.flag_bits & 0x1:
                raise ThemeError("Los temas cifrados no son compatibles.")
            if member.file_size > MAX_THEME_MEMBER_BYTES:
                raise ThemeError("El paquete contiene un archivo demasiado grande.")
            compressed = max(1, int(member.compress_size or 0))
            if member.file_size and member.file_size / compressed > MAX_THEME_COMPRESSION_RATIO:
                raise ThemeError("El paquete contiene compresión sospechosa.")
            total += member.file_size
            if total > MAX_THEME_UNPACKED_BYTES:
                raise ThemeError("El paquete supera el límite descomprimido de 100 MB.")
            target = (destination / safe_name).resolve()
            if not is_within_directory(target, destination):
                raise ThemeError("El paquete contiene rutas no seguras.")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)


def condition_matches(condition: str, context: Dict[str, Any]) -> bool:
    """Evalúa un vocabulario pequeño de condiciones, jamás Python arbitrario."""
    condition = (condition or "always").strip().lower()
    negate = condition.startswith("not:")
    if negate:
        condition = condition[4:]

    if condition in {"", "always", "true"}:
        result = True
    elif condition in {"never", "false"}:
        result = False
    elif condition == "controller.connected":
        result = bool(context.get("connected"))
    elif condition == "controller.disconnected":
        result = not bool(context.get("connected"))
    elif condition == "battery.charging":
        result = bool(context.get("is_charging"))
    elif condition == "battery.low":
        try:
            result = int(context.get("battery", 100)) < 20
        except (TypeError, ValueError, OverflowError):
            result = False
    elif condition.startswith("profile:"):
        result = str(context.get("active_profile_id", "")) == condition.split(":", 1)[1]
    elif condition.startswith("connection:"):
        result = str(context.get("connection_type", "")).lower() == condition.split(":", 1)[1]
    else:
        result = False

    return not result if negate else result


def substitute_variables(text: str, context: Dict[str, Any]) -> str:
    values = dict(VARIABLES)
    values.update({key: "" if value is None else value for key, value in context.items()})

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return str(values.get(key, match.group(0)))

    return re.sub(r"\{([A-Za-z0-9_.-]+)\}", replace, str(text or ""))
