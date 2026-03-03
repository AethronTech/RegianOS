"""Tests voor regian/skills/backup.py — backup en restore van de werkmap."""

import zipfile
from pathlib import Path

import pytest


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def backup_env(tmp_path, monkeypatch):
    """Tijdelijke werkmap + backup-map, beide geïsoleerd van het echte systeem."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    bkdir = tmp_path / "backups"
    bkdir.mkdir()

    monkeypatch.setenv("REGIAN_ROOT_DIR", str(workspace))
    monkeypatch.setenv("BACKUP_DIR", str(bkdir))
    monkeypatch.setenv("BACKUP_MAX_COUNT", "3")

    import regian.settings as s
    monkeypatch.setattr(s, "get_root_dir", lambda: str(workspace))
    monkeypatch.setattr(s, "get_backup_dir", lambda: str(bkdir))
    monkeypatch.setattr(s, "get_backup_max_count", lambda: 3)

    import regian.skills.backup as bk
    monkeypatch.setattr(bk, "get_root_dir", lambda: str(workspace))
    monkeypatch.setattr(bk, "get_backup_dir", lambda: str(bkdir))
    monkeypatch.setattr(bk, "get_backup_max_count", lambda: 3)

    return workspace, bkdir


# ── backup_workspace ──────────────────────────────────────────────────────────

def test_backup_workspace_creates_zip(backup_env):
    """Backup maakt een .zip aan in de backup-map."""
    workspace, bkdir = backup_env
    (workspace / "test.txt").write_text("hallo", encoding="utf-8")

    from regian.skills.backup import backup_workspace
    result = backup_workspace()

    assert "✅" in result
    zips = list(bkdir.glob("*.zip"))
    assert len(zips) == 1


def test_backup_workspace_zip_contains_file(backup_env):
    """De zip bevat de bestanden uit de werkmap."""
    workspace, bkdir = backup_env
    (workspace / "data.txt").write_text("inhoud", encoding="utf-8")

    from regian.skills.backup import backup_workspace
    backup_workspace()

    zip_path = list(bkdir.glob("*.zip"))[0]
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
    # Bestand staat relatief t.o.v. parent van workspace → "workspace/data.txt"
    assert any("data.txt" in n for n in names)


def test_backup_workspace_nonexistent_root(tmp_path, monkeypatch):
    """Geeft foutmelding als werkmap niet bestaat."""
    nonexistent = tmp_path / "bestaat_niet"
    bkdir = tmp_path / "backups"
    bkdir.mkdir()

    monkeypatch.setenv("REGIAN_ROOT_DIR", str(nonexistent))
    monkeypatch.setenv("BACKUP_DIR", str(bkdir))

    import regian.skills.backup as bk
    monkeypatch.setattr(bk, "get_root_dir", lambda: str(nonexistent))
    monkeypatch.setattr(bk, "get_backup_dir", lambda: str(bkdir))
    monkeypatch.setattr(bk, "get_backup_max_count", lambda: 5)

    result = bk.backup_workspace()
    assert "❌" in result


def test_backup_prunes_old_backups(backup_env):
    """Na max+1 backups wordt de oudste verwijderd."""
    workspace, bkdir = backup_env
    (workspace / "f.txt").write_text("x", encoding="utf-8")

    from regian.skills.backup import backup_workspace
    # Maak 4 backups (max=3 → 1 wordt gepruned)
    for _ in range(4):
        backup_workspace()

    zips = sorted(bkdir.glob("*.zip"))
    assert len(zips) == 3


# ── list_backups ──────────────────────────────────────────────────────────────

def test_list_backups_no_backups(backup_env):
    """Melding als er geen backups zijn."""
    from regian.skills.backup import list_backups
    result = list_backups()
    assert "Geen backups" in result


def test_list_backups_shows_filenames(backup_env):
    """Overzicht toont de backup-bestandsnamen."""
    workspace, bkdir = backup_env
    (workspace / "f.txt").write_text("x", encoding="utf-8")

    from regian.skills.backup import backup_workspace, list_backups
    backup_workspace()
    result = list_backups()

    assert "📦" in result
    assert "_workspace_backup.zip" in result


# ── restore_workspace ─────────────────────────────────────────────────────────

def test_restore_workspace_restores_file(backup_env):
    """Restore zet het bestand terug in de werkmap."""
    workspace, bkdir = backup_env
    (workspace / "restore_me.txt").write_text("origineel", encoding="utf-8")

    from regian.skills.backup import backup_workspace, restore_workspace
    backup_workspace()
    zip_name = list(bkdir.glob("*.zip"))[0].name

    # Verwijder het bestand na de backup
    (workspace / "restore_me.txt").unlink()
    assert not (workspace / "restore_me.txt").exists()

    result = restore_workspace(zip_name)
    assert "✅" in result
    assert (workspace / "restore_me.txt").exists()


def test_restore_workspace_missing_backup(backup_env):
    """Foutmelding als de backup-naam niet bestaat."""
    from regian.skills.backup import restore_workspace
    result = restore_workspace("bestaat_niet.zip")
    assert "❌" in result


def test_restore_workspace_shows_available_on_error(backup_env):
    """Foutmelding bij ontbrekende backup toont beschikbare backups."""
    workspace, bkdir = backup_env
    (workspace / "f.txt").write_text("x", encoding="utf-8")

    from regian.skills.backup import backup_workspace, restore_workspace
    backup_workspace()

    result = restore_workspace("wrong_name.zip")
    assert "❌" in result
    assert "_workspace_backup.zip" in result
