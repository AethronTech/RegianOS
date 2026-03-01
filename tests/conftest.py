# tests/conftest.py
"""
Gedeelde fixtures voor alle tests.
Isoleert elke test van het echte .env-bestand en de echte werkmap.
"""
import os
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch, tmp_path):
    """
    Voorkom dat tests echte .env schrijven of lezen.
    Overschrijft REGIAN_ROOT_DIR met een tijdelijke map.
    """
    monkeypatch.setenv("REGIAN_ROOT_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("CONFIRM_REQUIRED", "repo_delete,delete_file,delete_directory")
    monkeypatch.delenv("DANGEROUS_PATTERNS", raising=False)
    yield


@pytest.fixture
def tmp_root(tmp_path, monkeypatch):
    """
    Geeft een tijdelijke werkmap terug en patcht get_root_dir zodat alle
    file-skills daarheen schrijven (nooit naar de echte REGIAN_ROOT_DIR).
    """
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setenv("REGIAN_ROOT_DIR", str(root))
    # Patch ook de functie zelf zodat gecachede referenties in files.py meewerken
    import regian.settings as settings_mod
    monkeypatch.setattr(settings_mod, "get_root_dir", lambda: str(root))
    import regian.skills.files as files_mod
    monkeypatch.setattr(files_mod, "get_root_dir", lambda: str(root))
    return root


@pytest.fixture
def tmp_env_file(tmp_path):
    """Geeft een tijdelijk .env-bestand terug voor settings-tests."""
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    return env_file
