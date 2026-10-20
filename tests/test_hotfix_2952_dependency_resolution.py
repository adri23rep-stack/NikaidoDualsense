"""Regresiones del hotfix 2.9.5.2 para resolución de dependencias."""

from pathlib import Path

from packaging.requirements import Requirement
from packaging.version import Version


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_REQUIREMENTS = ROOT / "requirements-runtime.txt"


def _runtime_requirements() -> list[Requirement]:
    parsed: list[Requirement] = []
    for raw_line in RUNTIME_REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        parsed.append(Requirement(line))
    return parsed


def _requirement_named(name: str) -> Requirement:
    for requirement in _runtime_requirements():
        if requirement.name.lower() == name.lower():
            return requirement
    raise AssertionError(f"No se encontró la dependencia {name}")


def test_pycaw_pin_accepts_the_published_release():
    requirement = _requirement_named("pycaw")
    assert Version("20251023") in requirement.specifier
    assert str(requirement.specifier) == "==20251023"


def test_all_simple_runtime_ranges_accept_their_declared_minimum_or_exact_pin():
    """Evita rangos imposibles como ``>=20251023,<2027``."""
    for requirement in _runtime_requirements():
        candidates: list[Version] = []
        for specifier in requirement.specifier:
            if specifier.operator in {"==", ">=", "~="} and "*" not in specifier.version:
                candidates.append(Version(specifier.version))
        assert candidates, f"{requirement.name} no declara una versión mínima o exacta comprobable"
        assert any(candidate in requirement.specifier for candidate in candidates), (
            f"Rango imposible o contradictorio para {requirement}: "
            f"ninguna versión base {candidates} satisface el rango"
        )


def test_pycaw_requirement_is_only_enabled_on_windows():
    requirement = _requirement_named("pycaw")
    assert requirement.marker is not None
    assert requirement.marker.evaluate({"platform_system": "Windows"})
    assert not requirement.marker.evaluate({"platform_system": "Linux"})


def test_audio_repair_and_installer_use_the_same_requirement_source():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    installer = (ROOT / "install.bat").read_text(encoding="utf-8")
    repair = (ROOT / "REPARAR_GUI_Y_AUDIO.bat").read_text(encoding="utf-8")

    assert "-r requirements-runtime.txt" in requirements
    assert "-r requirements.txt" in installer
    assert "-r requirements.txt" in repair
