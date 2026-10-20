"""Auditor de privacidad para releases de Nikaido DualSense.

Privacy Auditor 2.0 separa datos realmente pertenecientes al equipo de
compilación de metadatos históricos incluidos por dependencias nativas.

Reglas principales:
- Cualquier término del entorno actual o ``NIKAIDO_PRIVACY_TERMS`` bloquea.
- Las rutas de usuario encontradas en archivos propios de texto/datos bloquean.
- Las rutas de otros compiladores dentro de DLL/PYD/EXE se reportan como aviso,
  pero no bloquean salvo que coincidan con el equipo actual o se active el modo
  estricto mediante ``NIKAIDO_PRIVACY_STRICT_THIRD_PARTY=1``.
- Los nombres mostrados en reportes se mantienen relativos para no filtrar la
  ruta local donde se construyó el programa.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

CHUNK_SIZE = 4 * 1024 * 1024
CHUNK_OVERLAP = 4096
MAX_ERROR_FINDINGS = 40
MAX_WARNING_FINDINGS = 80
MAX_FINDINGS = MAX_ERROR_FINDINGS + MAX_WARNING_FINDINGS

GENERIC_USER_NAMES = {
    "all users",
    "default",
    "default user",
    "example",
    "exampleuser",
    "public",
    "root",
    "user",
    "username",
    "usuario",
}

ARCHIVE_SUFFIXES = {".zip", ".whl", ".pyz"}
NATIVE_SUFFIXES = {".dll", ".exe", ".pyd", ".so", ".dylib", ".node"}
MEDIA_SUFFIXES = {
    ".bmp", ".gif", ".ico", ".jpeg", ".jpg", ".png", ".webp",
    ".mp3", ".ogg", ".wav", ".flac",
}
TEXT_SUFFIXES = {
    ".bat",
    ".cfg",
    ".cmd",
    ".css",
    ".csv",
    ".ini",
    ".iss",
    ".json",
    ".log",
    ".md",
    ".ps1",
    ".py",
    ".pyi",
    ".pyw",
    ".qss",
    ".rst",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

THIRD_PARTY_PARTS = {
    "comtypes",
    "hidapi",
    "pillow",
    "pil",
    "psutil",
    "pycaw",
    "pydualsense",
    "pyside6",
    "pystray",
    "qt-plugins",
    "shiboken6",
    "vgamepad",
    "win32",
}

_WINDOWS_USER_PATH = re.compile(rb"(?i)[a-z]:[\\/]+users[\\/]+([a-z0-9._-]+)")
_POSIX_USER_PATH = re.compile(rb"(?i)/(?:home|users)/([a-z0-9._-]+)")
_WINDOWS_USER_TEXT = re.compile(r"(?i)[a-z]:[\\/]+users[\\/]+([^\\/\x00\r\n]+)")
_POSIX_USER_TEXT = re.compile(r"(?i)/(?:home|users)/([^/\x00\r\n]+)")


@dataclass(frozen=True)
class PrivacyFinding:
    file: str
    kind: str
    value: str
    severity: str = "error"
    origin: str = "release"

    def describe(self, *, reveal_value: bool = False) -> str:
        if reveal_value:
            suffix = f" ({self.value})"
        elif self.severity == "error":
            suffix = " (valor privado oculto)"
        else:
            suffix = ""
        return f"{self.file}: {self.kind}{suffix}"


def _append_findings(target: list[PrivacyFinding], incoming: Iterable[PrivacyFinding]) -> None:
    """Añade hallazgos sin permitir que avisos oculten errores posteriores."""
    seen = set(target)
    errors = sum(item.severity == "error" for item in target)
    warnings = sum(item.severity != "error" for item in target)
    for item in incoming:
        if item in seen:
            continue
        if item.severity == "error":
            if errors >= MAX_ERROR_FINDINGS:
                continue
            errors += 1
        else:
            if warnings >= MAX_WARNING_FINDINGS:
                continue
            warnings += 1
        target.append(item)
        seen.add(item)


def _error_limit_reached(findings: Sequence[PrivacyFinding]) -> bool:
    return sum(item.severity == "error" for item in findings) >= MAX_ERROR_FINDINGS


@dataclass(frozen=True)
class PrivacyAuditReport:
    findings: tuple[PrivacyFinding, ...]
    files_scanned: int
    archives_scanned: int
    strict_third_party: bool

    @property
    def errors(self) -> tuple[PrivacyFinding, ...]:
        return tuple(item for item in self.findings if item.severity == "error")

    @property
    def warnings(self) -> tuple[PrivacyFinding, ...]:
        return tuple(item for item in self.findings if item.severity != "error")

    @property
    def passed(self) -> bool:
        return not self.errors


def _clean_term(value: object) -> str:
    return str(value or "").strip().strip('"\'')


def _env_flag(name: str, default: bool = False) -> bool:
    raw = _clean_term(os.environ.get(name, ""))
    if not raw:
        return default
    return raw.casefold() in {"1", "true", "yes", "on", "si", "sí"}


def collect_sensitive_terms(environ: dict[str, str] | None = None) -> tuple[str, ...]:
    """Obtiene identidad/rutas del entorno sin guardarlas en el repositorio."""
    env = dict(os.environ if environ is None else environ)
    raw: list[str] = []
    for key in ("USERNAME", "USER", "USERPROFILE", "HOME", "COMPUTERNAME"):
        value = _clean_term(env.get(key, ""))
        if value:
            raw.append(value)
    for key in ("USERPROFILE", "HOME"):
        value = _clean_term(env.get(key, ""))
        if value:
            raw.append(Path(value.replace("\\", "/")).name)
    raw.extend(
        item.strip()
        for item in re.split(r"[;\r\n]+", _clean_term(env.get("NIKAIDO_PRIVACY_TERMS", "")))
        if item.strip()
    )

    terms: dict[str, str] = {}
    for value in raw:
        variants = {value, value.replace("\\", "/"), value.replace("/", "\\")}
        for variant in variants:
            normalized = variant.casefold().strip()
            if len(normalized) < 3 or normalized in GENERIC_USER_NAMES:
                continue
            terms.setdefault(normalized, variant)
    return tuple(terms[key] for key in sorted(terms))


def _needle_variants(term: str) -> tuple[bytes, ...]:
    variants = {
        term.casefold().encode("utf-8", "ignore"),
        term.casefold().encode("utf-16le", "ignore"),
    }
    return tuple(item for item in variants if item)


def _sensitive_usernames(terms: Sequence[str]) -> set[str]:
    users: set[str] = set()
    for term in terms:
        cleaned = _clean_term(term).replace("\\", "/")
        if not cleaned:
            continue
        windows = re.search(r"(?i)[a-z]:/+users/+([^/]+)", cleaned)
        posix = re.search(r"(?i)/(?:home|users)/+([^/]+)", cleaned)
        if windows:
            users.add(windows.group(1).casefold())
        if posix:
            users.add(posix.group(1).casefold())
        leaf = cleaned.rstrip("/").rsplit("/", 1)[-1].casefold()
        if 3 <= len(leaf) <= 80 and leaf not in GENERIC_USER_NAMES:
            users.add(leaf)
        if "/" not in cleaned and 3 <= len(cleaned) <= 80:
            users.add(cleaned.casefold())
    return users


def _file_kind(label: str) -> tuple[str, str]:
    """Devuelve (tipo, origen) usando solamente la ruta relativa segura."""
    member = label.split("!", 1)[-1]
    path = Path(member.replace("\\", "/"))
    suffix = path.suffix.casefold()
    parts = {part.casefold() for part in path.parts}
    third_party = bool(parts & THIRD_PARTY_PARTS)
    if suffix in NATIVE_SUFFIXES:
        return "native", "third_party" if third_party else "native"
    if suffix in MEDIA_SUFFIXES:
        return "media", "third_party" if third_party else "owned"
    if suffix in TEXT_SUFFIXES:
        return "text", "third_party" if third_party else "owned"
    if suffix in ARCHIVE_SUFFIXES:
        return "archive", "third_party" if third_party else "release"
    return "data", "third_party" if third_party else "owned"


def _decoded_path_matches(data: bytes) -> list[str]:
    matches: list[str] = []
    lowered = data.lower()
    for regex in (_WINDOWS_USER_PATH, _POSIX_USER_PATH):
        for match in regex.finditer(lowered):
            matches.append(match.group(1).decode("utf-8", "replace").strip().casefold())

    try:
        text16 = data.decode("utf-16le", "ignore")
    except Exception:
        text16 = ""
    for regex in (_WINDOWS_USER_TEXT, _POSIX_USER_TEXT):
        for match in regex.finditer(text16):
            matches.append(match.group(1).strip().casefold())
    return matches


def _path_user_findings(
    data: bytes,
    *,
    label: str,
    terms: Sequence[str],
    strict_third_party: bool,
) -> Iterator[PrivacyFinding]:
    sensitive_users = _sensitive_usernames(terms)
    file_kind, origin = _file_kind(label)
    for username in _decoded_path_matches(data):
        if not username or username in GENERIC_USER_NAMES:
            continue
        if username in sensitive_users:
            yield PrivacyFinding(
                label,
                "ruta privada del entorno de compilación",
                username,
                "error",
                origin,
            )
            continue
        if file_kind == "native":
            severity = "error" if strict_third_party else "warning"
            yield PrivacyFinding(
                label,
                "metadato histórico de compilación en binario nativo",
                username,
                severity,
                origin,
            )
            continue
        if origin == "third_party":
            severity = "error" if strict_third_party else "warning"
            yield PrivacyFinding(
                label,
                "ruta histórica incluida por dependencia",
                username,
                severity,
                origin,
            )
            continue
        yield PrivacyFinding(
            label,
            "ruta de usuario dentro de archivo distribuido",
            username,
            "error",
            origin,
        )


def scan_bytes(
    data: bytes,
    *,
    label: str,
    terms: Sequence[str],
    strict_third_party: bool = False,
) -> list[PrivacyFinding]:
    findings: list[PrivacyFinding] = []
    lowered = data.lower()
    file_kind, origin = _file_kind(label)
    # Los formatos de imagen/audio comprimidos pueden contener por casualidad
    # secuencias cortas iguales al usuario del equipo. Buscar términos sueltos
    # dentro de esos bytes produce falsos positivos; las rutas completas siguen
    # analizándose abajo y los textos, .bin y binarios nativos sí se inspeccionan.
    if file_kind != "media":
        for term in terms:
            for needle in _needle_variants(term):
                if needle in lowered:
                    findings.append(
                        PrivacyFinding(label, "término privado", term, "error", origin)
                    )
                    break
            if len(findings) >= MAX_FINDINGS:
                return list(dict.fromkeys(findings))[:MAX_FINDINGS]

    for finding in _path_user_findings(
        data,
        label=label,
        terms=terms,
        strict_third_party=strict_third_party,
    ):
        findings.append(finding)
        if len(findings) >= MAX_FINDINGS:
            break
    return list(dict.fromkeys(findings))[:MAX_FINDINGS]


def _scan_regular_file(
    path: Path,
    *,
    label: str,
    terms: Sequence[str],
    strict_third_party: bool,
) -> list[PrivacyFinding]:
    findings: list[PrivacyFinding] = []
    previous = b""
    try:
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                block = previous + chunk
                _append_findings(
                    findings,
                    scan_bytes(
                        block,
                        label=label,
                        terms=terms,
                        strict_third_party=strict_third_party,
                    ),
                )
                if _error_limit_reached(findings):
                    break
                previous = block[-CHUNK_OVERLAP:]
    except OSError:
        return []
    return findings


def _scan_zip(
    path: Path,
    *,
    label: str,
    terms: Sequence[str],
    strict_third_party: bool,
) -> list[PrivacyFinding]:
    findings: list[PrivacyFinding] = []
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                member_label = f"{label}!{info.filename}"
                _append_findings(
                    findings,
                    scan_bytes(
                        info.filename.encode("utf-8", "ignore"),
                        label=member_label,
                        terms=terms,
                        strict_third_party=strict_third_party,
                    ),
                )
                if _error_limit_reached(findings):
                    break
                with archive.open(info) as stream:
                    previous = b""
                    while True:
                        chunk = stream.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        block = previous + chunk
                        _append_findings(
                            findings,
                            scan_bytes(
                                block,
                                label=member_label,
                                terms=terms,
                                strict_third_party=strict_third_party,
                            ),
                        )
                        if _error_limit_reached(findings):
                            break
                        previous = block[-CHUNK_OVERLAP:]
                if _error_limit_reached(findings):
                    break
    except (OSError, zipfile.BadZipFile, RuntimeError):
        return []
    return findings


def _iter_labeled_files(paths: Iterable[Path]) -> Iterator[tuple[Path, str]]:
    """Itera archivos con etiquetas relativas que nunca revelan la ruta local."""
    seen: set[Path] = set()
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                yield path, path.name
        elif path.is_dir():
            root_label = path.name or "release"
            for child in sorted(path.rglob("*")):
                if not child.is_file():
                    continue
                resolved = child.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                relative = child.relative_to(path).as_posix()
                yield child, f"{root_label}/{relative}"


def iter_files(paths: Iterable[Path]) -> Iterator[Path]:
    """Compatibilidad con el auditor anterior: devuelve solo rutas físicas."""
    for path, _label in _iter_labeled_files(paths):
        yield path


def audit_paths_detailed(
    paths: Iterable[Path | str],
    *,
    terms: Sequence[str] | None = None,
    strict_third_party: bool | None = None,
) -> PrivacyAuditReport:
    """Escanea release y separa errores reales de avisos de terceros."""
    selected_terms = tuple(collect_sensitive_terms() if terms is None else terms)
    strict = (
        _env_flag("NIKAIDO_PRIVACY_STRICT_THIRD_PARTY")
        if strict_third_party is None
        else bool(strict_third_party)
    )
    findings: list[PrivacyFinding] = []
    files_scanned = 0
    archives_scanned = 0

    for path, label in _iter_labeled_files(Path(item) for item in paths):
        files_scanned += 1
        if path.suffix.casefold() in ARCHIVE_SUFFIXES:
            archives_scanned += 1
            current = _scan_zip(
                path,
                label=label,
                terms=selected_terms,
                strict_third_party=strict,
            )
        else:
            current = _scan_regular_file(
                path,
                label=label,
                terms=selected_terms,
                strict_third_party=strict,
            )
        _append_findings(findings, current)
        if _error_limit_reached(findings):
            break

    ordered = tuple(
        [item for item in findings if item.severity == "error"]
        + [item for item in findings if item.severity != "error"]
    )
    return PrivacyAuditReport(ordered, files_scanned, archives_scanned, strict)


def audit_paths(
    paths: Iterable[Path | str],
    *,
    terms: Sequence[str] | None = None,
    strict_third_party: bool | None = None,
) -> list[PrivacyFinding]:
    """Compatibilidad: devuelve solamente hallazgos que bloquean la release."""
    return list(
        audit_paths_detailed(
            paths,
            terms=terms,
            strict_third_party=strict_third_party,
        ).errors
    )


def write_audit_report(report: PrivacyAuditReport, destination: Path | str) -> Path:
    """Escribe un comprobante distribuible sin valores privados ni rutas locales."""
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 2,
        "product": "Nikaido DualSense",
        "result": "passed" if report.passed else "blocked",
        "files_scanned": report.files_scanned,
        "archives_scanned": report.archives_scanned,
        "blocking_findings": len(report.errors),
        "native_metadata_warnings": len(report.warnings),
        "strict_third_party": report.strict_third_party,
        "policy": {
            "environment_terms": "blocking",
            "owned_file_user_paths": "blocking",
            "foreign_native_build_metadata": (
                "blocking" if report.strict_third_party else "warning"
            ),
            "values_redacted": True,
        },
        "findings": [
            {
                "file": item.file,
                "kind": item.kind,
                "severity": item.severity,
                "origin": item.origin,
                "value": "<redacted>",
            }
            for item in report.findings
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def require_private_release(paths: Iterable[Path | str]) -> PrivacyAuditReport:
    """Bloquea solo filtraciones atribuibles al equipo de compilación actual."""
    report = audit_paths_detailed(paths)
    if report.warnings:
        print(
            "  Auditoría de privacidad: "
            f"{len(report.warnings)} metadato(s) nativo(s) de terceros reportados sin bloquear."
        )
        for item in report.warnings[:6]:
            print(f"    Aviso: {item.file}: {item.kind}")
        if len(report.warnings) > 6:
            print(f"    ... y {len(report.warnings) - 6} aviso(s) adicional(es).")

    if report.errors:
        reveal = _env_flag("NIKAIDO_PRIVACY_SHOW_VALUES")
        details = "\n".join(
            f"- {item.describe(reveal_value=reveal)}" for item in report.errors
        )
        raise RuntimeError(
            "La auditoría de privacidad detectó datos atribuibles al equipo de compilación:\n"
            f"{details}\n"
            "Limpia esos datos o agrega términos privados con NIKAIDO_PRIVACY_TERMS. "
            "Los metadatos históricos de DLL de terceros ya no bloquean por defecto."
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditar privacidad de una release de Nikaido")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--json-report", type=Path, default=None)
    parser.add_argument(
        "--strict-third-party",
        action="store_true",
        help="Tratar rutas históricas de DLL externas como errores",
    )
    args = parser.parse_args()
    report = audit_paths_detailed(
        args.paths,
        strict_third_party=args.strict_third_party,
    )
    if args.json_report:
        write_audit_report(report, args.json_report)
    if report.errors:
        print("AUDITORÍA DE PRIVACIDAD FALLIDA")
        for finding in report.errors:
            print(f"- {finding.describe()}")
        return 1
    print("Auditoría de privacidad aprobada")
    if report.warnings:
        print(
            f"Avisos informativos de metadatos nativos externos: {len(report.warnings)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
