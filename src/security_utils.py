"""Utilidades pequeñas de seguridad para entradas, archivos y reportes locales.

No hacen llamadas de red ni ejecutan comandos. Centralizar estas reglas evita
que cada importador implemente límites distintos o termine confiando en rutas
incluidas dentro de un archivo externo.
"""

from __future__ import annotations

import json
import math
import os
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any, Mapping


class SecurityValidationError(ValueError):
    """Entrada rechazada porque supera límites o contiene una ruta insegura."""


def validate_json_complexity(
    value: Any,
    *,
    label: str = "JSON",
    max_depth: int = 24,
    max_nodes: int = 50_000,
    max_string_length: int = 65_536,
    max_collection_items: int = 10_000,
) -> None:
    """Rechaza estructuras diseñadas para agotar memoria o recursión.

    ``json.loads`` evita ejecución de código, pero un JSON muy profundo o con
    cientos de miles de nodos todavía puede congelar una interfaz. El recorrido
    es iterativo para no caer en el mismo problema que intenta detectar.
    """

    stack: list[tuple[Any, int]] = [(value, 0)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > max_nodes:
            raise SecurityValidationError(
                f"{label} contiene demasiados valores (máximo {max_nodes})."
            )
        if depth > max_depth:
            raise SecurityValidationError(
                f"{label} está demasiado anidado (máximo {max_depth} niveles)."
            )
        if isinstance(current, str):
            if len(current) > max_string_length:
                raise SecurityValidationError(
                    f"{label} contiene un texto demasiado largo."
                )
            continue
        if isinstance(current, float) and not math.isfinite(current):
            raise SecurityValidationError(
                f"{label} contiene un número no finito."
            )
        if isinstance(current, Mapping):
            if len(current) > max_collection_items:
                raise SecurityValidationError(
                    f"{label} contiene demasiadas claves en un solo bloque."
                )
            for key, item in current.items():
                if len(str(key)) > 512:
                    raise SecurityValidationError(
                        f"{label} contiene una clave demasiado larga."
                    )
                stack.append((item, depth + 1))
            continue
        if isinstance(current, (list, tuple, set)):
            if len(current) > max_collection_items:
                raise SecurityValidationError(
                    f"{label} contiene una lista demasiado grande."
                )
            stack.extend((item, depth + 1) for item in current)


def safe_json_loads(
    payload: str | bytes,
    *,
    label: str = "JSON",
    max_bytes: int = 4 * 1024 * 1024,
    **complexity_limits: Any,
) -> Any:
    if isinstance(payload, bytes):
        if len(payload) > max_bytes:
            raise SecurityValidationError(f"{label} supera el límite de tamaño permitido.")
        try:
            text = payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise SecurityValidationError(f"{label} no usa UTF-8 válido.") from exc
    else:
        text = str(payload)
        if len(text.encode("utf-8")) > max_bytes:
            raise SecurityValidationError(f"{label} supera el límite de tamaño permitido.")
    def reject_constant(value: str) -> None:
        raise SecurityValidationError(
            f"{label} contiene una constante numérica no válida ({value})."
        )

    try:
        value = json.loads(text, parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise SecurityValidationError(
            f"{label} contiene JSON inválido en la línea {exc.lineno}."
        ) from exc
    validate_json_complexity(value, label=label, **complexity_limits)
    return value


def read_json_file_limited(
    path: Path,
    *,
    label: str = "JSON",
    max_bytes: int = 4 * 1024 * 1024,
    **complexity_limits: Any,
) -> Any:
    path = Path(path)
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise SecurityValidationError(f"No se pudo leer {label}.") from exc
    if size > max_bytes:
        raise SecurityValidationError(f"{label} supera el límite de tamaño permitido.")
    return safe_json_loads(
        path.read_bytes(),
        label=label,
        max_bytes=max_bytes,
        **complexity_limits,
    )


def validate_zip_member_name(name: str, *, label: str = "paquete") -> str:
    """Devuelve un nombre POSIX normalizado o rechaza rutas ambiguas/peligrosas."""

    value = str(name or "")
    if not value or "\x00" in value or "\\" in value or len(value) > 240:
        raise SecurityValidationError(f"El {label} contiene un nombre de archivo inseguro.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise SecurityValidationError(f"El {label} contiene una ruta insegura.")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    for part in path.parts:
        if (
            ":" in part
            or any(ord(ch) < 32 for ch in part)
            or part.endswith((" ", "."))
            or part.split(".", 1)[0].upper() in reserved
        ):
            raise SecurityValidationError(
                f"El {label} contiene un nombre incompatible o ambiguo en Windows."
            )
    first = path.parts[0] if path.parts else ""
    if re.match(r"^[A-Za-z]:", first):
        raise SecurityValidationError(f"El {label} contiene una ruta de unidad insegura.")
    return path.as_posix()


def is_within_directory(path: Path, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (OSError, ValueError):
        return False


def harden_private_file(path: Path) -> None:
    """Aplica permisos de usuario donde el sistema los soporte."""

    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def redact_private_text(value: Any) -> str:
    """Oculta rutas de usuario y caracteres de control antes de compartir logs."""

    text = str(value or "")
    private_roots = {
        os.environ.get("USERPROFILE", ""),
        os.environ.get("APPDATA", ""),
        os.environ.get("LOCALAPPDATA", ""),
        os.environ.get("TEMP", ""),
        os.environ.get("TMP", ""),
        str(Path.home()),
    }
    for root in sorted((item for item in private_roots if item), key=len, reverse=True):
        text = text.replace(root, "<RUTA_USUARIO>")
        text = text.replace(root.replace("\\", "/"), "<RUTA_USUARIO>")
    for username in {os.environ.get("USERNAME", ""), os.environ.get("USER", "")}:
        if username and len(username) >= 3:
            text = re.sub(
                rf"(?i)(?<![A-Z0-9_]){re.escape(username)}(?![A-Z0-9_])",
                "<USUARIO>",
                text,
            )
    text = re.sub(
        r"(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\s]+(?:[\\/][^\s]*)?",
        "<RUTA_USUARIO>",
        text,
    )
    text = re.sub(
        r"(?i)/(?:home|users)/[^/\s]+(?:/[^\s]*)?",
        "<RUTA_USUARIO>",
        text,
    )
    # Evita que una excepción inyecte líneas falsas en reportes o registros.
    return "".join(ch if ch in "\n\t" or ord(ch) >= 32 else "?" for ch in text)
