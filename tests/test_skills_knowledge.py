# tests/test_skills_knowledge.py
"""Tests voor regian/skills/knowledge.py — kennisbank-beheer."""

import pytest
from pathlib import Path


# ── Hulpfunctie ───────────────────────────────────────────────────────────────

def _make_src_file(root: Path, name: str, content: str = "testinhoud") -> Path:
    """Maakt een bronbestand aan in de werkmap-root."""
    src = root / name
    src.write_text(content, encoding="utf-8")
    return src


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def patched_knowledge(tmp_root, monkeypatch):
    """
    Patcht get_root_dir en get_active_project zodat kennis-skills
    naar tmp_root/.regian_knowledge schrijven, zonder actief project.
    """
    import regian.settings as settings_mod
    import regian.skills.knowledge as km

    monkeypatch.setattr(settings_mod, "get_root_dir", lambda: str(tmp_root))
    monkeypatch.setattr(settings_mod, "get_active_project", lambda: None)

    # Zorg dat de knowledge-module dezelfde gepatchte functies gebruikt
    monkeypatch.setattr(km, "_get_knowledge_dir", lambda: tmp_root / ".regian_knowledge")
    return tmp_root


# ── Tests: add_to_knowledge ───────────────────────────────────────────────────

def test_add_to_knowledge_ok(tmp_root, monkeypatch):
    """Bestaand bestand wordt gekopieerd naar de kennisbank."""
    import regian.settings as settings_mod
    monkeypatch.setattr(settings_mod, "get_root_dir", lambda: str(tmp_root))
    monkeypatch.setattr(settings_mod, "get_active_project", lambda: None)

    _make_src_file(tmp_root, "spec.md", "# Specificatie\ninhoud hier")

    from regian.skills.knowledge import add_to_knowledge
    result = add_to_knowledge("spec.md")

    assert "✅" in result
    assert "spec.md" in result
    assert (tmp_root / ".regian_knowledge" / "spec.md").exists()


def test_add_to_knowledge_not_found(tmp_root, monkeypatch):
    """Niet-bestaand bestand geeft foutmelding."""
    import regian.settings as settings_mod
    monkeypatch.setattr(settings_mod, "get_root_dir", lambda: str(tmp_root))
    monkeypatch.setattr(settings_mod, "get_active_project", lambda: None)

    from regian.skills.knowledge import add_to_knowledge
    result = add_to_knowledge("bestaat_niet.txt")

    assert "❌" in result
    assert "bestaat_niet.txt" in result


def test_add_to_knowledge_creates_dir(tmp_root, monkeypatch):
    """De kennisbank-map wordt aangemaakt als ze nog niet bestaat."""
    import regian.settings as settings_mod
    monkeypatch.setattr(settings_mod, "get_root_dir", lambda: str(tmp_root))
    monkeypatch.setattr(settings_mod, "get_active_project", lambda: None)

    _make_src_file(tmp_root, "nieuw.txt")
    kdir = tmp_root / ".regian_knowledge"
    assert not kdir.exists()

    from regian.skills.knowledge import add_to_knowledge
    add_to_knowledge("nieuw.txt")

    assert kdir.exists()
    assert (kdir / "nieuw.txt").exists()


# ── Tests: list_knowledge ─────────────────────────────────────────────────────

def test_list_knowledge_empty(tmp_root, monkeypatch):
    """Lege kennisbank geeft 'leeg'-bericht."""
    import regian.settings as settings_mod
    monkeypatch.setattr(settings_mod, "get_root_dir", lambda: str(tmp_root))
    monkeypatch.setattr(settings_mod, "get_active_project", lambda: None)

    from regian.skills.knowledge import list_knowledge
    result = list_knowledge()

    assert "leeg" in result.lower() or "📭" in result


def test_list_knowledge_with_files(tmp_root, monkeypatch):
    """Kennisbank toont bestandsnamen en grootte."""
    import regian.settings as settings_mod
    monkeypatch.setattr(settings_mod, "get_root_dir", lambda: str(tmp_root))
    monkeypatch.setattr(settings_mod, "get_active_project", lambda: None)

    # Voeg eerst een bestand toe
    _make_src_file(tmp_root, "readme.md", "## Readme\ninhoud")
    from regian.skills.knowledge import add_to_knowledge, list_knowledge
    add_to_knowledge("readme.md")

    result = list_knowledge()
    assert "readme.md" in result
    assert "📚" in result or "Kennisbank" in result


# ── Tests: remove_from_knowledge ─────────────────────────────────────────────

def test_remove_knowledge_ok(tmp_root, monkeypatch):
    """Bestaand kennisbestand wordt verwijderd."""
    import regian.settings as settings_mod
    monkeypatch.setattr(settings_mod, "get_root_dir", lambda: str(tmp_root))
    monkeypatch.setattr(settings_mod, "get_active_project", lambda: None)

    _make_src_file(tmp_root, "temp.txt", "inhoud")
    from regian.skills.knowledge import add_to_knowledge, remove_from_knowledge
    add_to_knowledge("temp.txt")

    kfile = tmp_root / ".regian_knowledge" / "temp.txt"
    assert kfile.exists()

    result = remove_from_knowledge("temp.txt")
    assert "✅" in result
    assert not kfile.exists()


def test_remove_knowledge_not_found(tmp_root, monkeypatch):
    """Niet-bestaand kennisbestand geeft foutmelding."""
    import regian.settings as settings_mod
    monkeypatch.setattr(settings_mod, "get_root_dir", lambda: str(tmp_root))
    monkeypatch.setattr(settings_mod, "get_active_project", lambda: None)

    from regian.skills.knowledge import remove_from_knowledge
    result = remove_from_knowledge("fictief.txt")

    assert "❌" in result
    assert "fictief.txt" in result


# ── Tests: clear_knowledge ────────────────────────────────────────────────────

def test_clear_knowledge_with_files(tmp_root, monkeypatch):
    """Kennisbank wist alle bestanden en rapporteert het aantal."""
    import regian.settings as settings_mod
    monkeypatch.setattr(settings_mod, "get_root_dir", lambda: str(tmp_root))
    monkeypatch.setattr(settings_mod, "get_active_project", lambda: None)

    _make_src_file(tmp_root, "a.txt", "a")
    _make_src_file(tmp_root, "b.txt", "b")

    from regian.skills.knowledge import add_to_knowledge, clear_knowledge
    add_to_knowledge("a.txt")
    add_to_knowledge("b.txt")

    kdir = tmp_root / ".regian_knowledge"
    assert len(list(kdir.iterdir())) == 2

    result = clear_knowledge()
    assert "✅" in result
    assert not kdir.exists() or not any(kdir.iterdir())


def test_clear_knowledge_empty(tmp_root, monkeypatch):
    """Wissen van lege kennisbank geeft 'was al leeg'-melding."""
    import regian.settings as settings_mod
    monkeypatch.setattr(settings_mod, "get_root_dir", lambda: str(tmp_root))
    monkeypatch.setattr(settings_mod, "get_active_project", lambda: None)

    from regian.skills.knowledge import clear_knowledge
    result = clear_knowledge()

    assert "leeg" in result.lower() or "📭" in result
