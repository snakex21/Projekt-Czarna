"""Kontrakt artefaktów release/open-source (P5.1).

Te testy pilnują, że repozytorium ma minimalny zestaw plików potrzebnych do
publikacji: licencję, instrukcje kontrybucji, historię zmian i workflow CI.
"""
from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_license_exists_and_is_mit():
    license_path = PROJECT_ROOT / "LICENSE"
    assert license_path.exists(), "Brak LICENSE — P5.1 wymaga jawnej licencji"
    text = license_path.read_text(encoding="utf-8")
    assert "MIT License" in text
    assert "Permission is hereby granted" in text
    assert "Mapa Katastralna Czarna" in text or "Projekt Mapa Czarna" in text


def test_contributing_exists_with_project_conventions():
    text = _read("CONTRIBUTING.md")
    required = [
        "# CONTRIBUTING",
        "Python 3.11+",
        "FastAPI",
        "Tkinter",
        "TDD",
        "PROJECT_SKILL.md",
        "pytest",
        "Nie commituj sekretów",
    ]
    for phrase in required:
        assert phrase in text, f"CONTRIBUTING.md nie zawiera: {phrase}"


def test_changelog_exists_with_initial_release_section():
    text = _read("CHANGELOG.md")
    assert "# CHANGELOG" in text
    assert "## 1.0.0" in text or "## v1.0.0" in text
    for phrase in (
        "FastAPI",
        "launcher",
        "PostgreSQL",
        "diagnosty",
        "bezpieczeń",
        "P2.5",
    ):
        assert phrase.lower() in text.lower(), f"CHANGELOG.md nie zawiera: {phrase}"


def test_github_actions_ci_workflow_exists():
    workflow = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    assert workflow.exists(), "Brak .github/workflows/ci.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "python-version" in text
    assert "pip install -r requirements.txt" in text
    assert "python -m pytest" in text
    # Pełny zestaw bez wyjątków - dawne flaky testy zostały naprawione.
    assert "--ignore" not in text
    # Lint i audyt zależności.
    assert "ruff check" in text
    assert "pip-audit" in text
    assert (PROJECT_ROOT / "ruff.toml").exists()


def test_readme_mentions_release_artifacts():
    text = _read("README.md")
    assert "LICENSE" in text
    assert "CHANGELOG.md" in text
    assert "CONTRIBUTING.md" in text


def test_ci_installs_browser_test_dependencies():
    requirements = _read("requirements-test.txt")
    assert "-r requirements.txt" in requirements
    assert "pytest-playwright>=" in requirements
    assert "playwright>=" in requirements
    assert "Werkzeug>=" in _read("requirements.txt")
    workflow = _read(".github/workflows/ci.yml")
    assert "-r requirements-test.txt" in workflow
    assert "python -m playwright install chromium" in workflow


def test_readme_documents_setup_security_and_seed():
    text = _read("README.md")
    for phrase in (
        "backend/.env.example",
        "python -m backend.scripts.set_admin_password",
        "python -m backend.scripts.seed_demo",
        "python -m uvicorn backend.main:app",
        "ADMIN_PASSWORD_HASH",
        "SECRET_KEY_FILE",
        "### Bezpieczeństwo",
    ):
        assert phrase in text, f"README.md nie zawiera: {phrase}"
    assert "admin123" not in text
    assert "TODO.md" not in text


def test_env_example_has_no_secrets():
    text = _read("backend/.env.example")
    values = dict(
        line.split("=", 1) for line in text.splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    for key in ("DB_PASSWORD", "FLASK_SECRET_KEY", "ADMIN_PASSWORD_HASH"):
        assert key in values and values[key].strip() == "", key
