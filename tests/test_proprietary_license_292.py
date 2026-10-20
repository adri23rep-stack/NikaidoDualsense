from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_current_release_is_proprietary_and_names_owner():
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert license_text.rstrip().endswith("© Team Nikaido")
    assert "Team Nikaido" not in "\n".join(license_text.splitlines()[:-1])
    assert "Todos los derechos reservados" in license_text
    assert "NO SE CONCEDE PERMISO" in license_text
    assert "MIT License" not in license_text
    assert "license-Proprietary" in readme
    assert "licencia MIT" not in readme


def test_eulas_cover_demo_paid_no_redistribution_and_third_party_rights():
    for name in ("EULA_ES.txt", "EULA_EN.txt", "EULA_PT_BR.txt", "EULA_NIKAIDO.txt"):
        assert (ROOT / name).is_file()
    es = (ROOT / "EULA_ES.txt").read_text(encoding="utf-8")
    assert "EDICIÓN DEMO" in es
    assert "EDICIÓN COMPLETA" in es
    assert "copiar o redistribuir" in es
    assert "COMPONENTES DE TERCEROS" in es
    assert "leyes de los Estados Unidos Mexicanos" in es


def test_installer_and_build_embed_proprietary_legal_documents():
    installer = (ROOT / "installer" / "Nikaido.iss").read_text(encoding="utf-8")
    build = (ROOT / "build.py").read_text(encoding="utf-8")
    assert "LicenseFile=..\\EULA_NIKAIDO.txt" in installer
    assert "Team Nikaido" in installer
    assert "LegalCopyright" in build
    assert "copy_legal_documents(onefile=onefile)" in build
    assert "THIRD_PARTY_LICENSES" in build


def test_owner_name_is_only_at_the_end_of_each_visible_license():
    for name in ("LICENSE", "EULA_ES.txt", "EULA_EN.txt", "EULA_PT_BR.txt", "EULA_NIKAIDO.txt"):
        lines = (ROOT / name).read_text(encoding="utf-8").strip().splitlines()
        assert lines[-1] == "© Team Nikaido"
        assert all("Team Nikaido" not in line for line in lines[:-1])
