# tests/test_skills_files.py
"""Tests voor regian/skills/files.py — bestandsoperaties met tijdelijke map."""
import pytest
from pathlib import Path


# ── Fixtures ───────────────────────────────────────────────────────────────────

# Alle tests in deze module gebruiken tmp_root via conftest.py


# ── write_file / read_file ─────────────────────────────────────────────────────

class TestWriteReadFile:
    def test_write_and_read_roundtrip(self, tmp_root):
        from regian.skills.files import write_file, read_file
        write_file("hello.txt", "Hallo wereld")
        result = read_file("hello.txt")
        assert result == "Hallo wereld"

    def test_write_creates_parent_dirs(self, tmp_root):
        from regian.skills.files import write_file
        result = write_file("subdir/nested/file.txt", "inhoud")
        assert "Succes" in result
        assert (tmp_root / "subdir" / "nested" / "file.txt").exists()

    def test_write_returns_success_message(self, tmp_root):
        from regian.skills.files import write_file
        result = write_file("test.txt", "data")
        assert "Succes" in result

    def test_read_nonexistent_file(self, tmp_root):
        from regian.skills.files import read_file
        result = read_file("bestaat_niet.txt")
        assert "Fout" in result or "bestaat niet" in result.lower()

    def test_write_overwrites_existing(self, tmp_root):
        from regian.skills.files import write_file, read_file
        write_file("overwrite.txt", "eerste")
        write_file("overwrite.txt", "tweede")
        assert read_file("overwrite.txt") == "tweede"

    def test_write_unicode_content(self, tmp_root):
        from regian.skills.files import write_file, read_file
        write_file("unicode.txt", "héllo wörld 🚀")
        assert read_file("unicode.txt") == "héllo wörld 🚀"


# ── list_directory ─────────────────────────────────────────────────────────────

class TestListDirectory:
    def test_list_empty_dir(self, tmp_root):
        from regian.skills.files import list_directory
        result = list_directory(".")
        assert isinstance(result, list)

    def test_list_shows_created_file(self, tmp_root):
        from regian.skills.files import write_file, list_directory
        write_file("visible.txt", "x")
        result = list_directory(".")
        assert "visible.txt" in result

    def test_list_nonexistent_dir(self, tmp_root):
        from regian.skills.files import list_directory
        result = list_directory("bestaat_niet_map")
        assert "Fout" in result or isinstance(result, str)

    def test_list_returns_subdirs(self, tmp_root):
        from regian.skills.files import create_directory, list_directory
        create_directory("submap")
        result = list_directory(".")
        assert "submap" in result


# ── create_directory ───────────────────────────────────────────────────────────

class TestCreateDirectory:
    def test_creates_new_dir(self, tmp_root):
        from regian.skills.files import create_directory
        result = create_directory("nieuwe_map")
        assert "Succes" in result
        assert (tmp_root / "nieuwe_map").is_dir()

    def test_creates_nested_dirs(self, tmp_root):
        from regian.skills.files import create_directory
        result = create_directory("a/b/c")
        assert "Succes" in result
        assert (tmp_root / "a" / "b" / "c").is_dir()

    def test_idempotent_on_existing(self, tmp_root):
        from regian.skills.files import create_directory
        create_directory("bestaat_al")
        result = create_directory("bestaat_al")
        assert "Succes" in result


# ── delete_file ────────────────────────────────────────────────────────────────

class TestDeleteFile:
    def test_delete_existing_file(self, tmp_root):
        from regian.skills.files import write_file, delete_file
        write_file("te_verwijderen.txt", "data")
        result = delete_file("te_verwijderen.txt")
        assert "Succes" in result
        assert not (tmp_root / "te_verwijderen.txt").exists()

    def test_delete_nonexistent_file(self, tmp_root):
        from regian.skills.files import delete_file
        result = delete_file("bestaat_niet.txt")
        assert "Fout" in result


# ── delete_directory ───────────────────────────────────────────────────────────

class TestDeleteDirectory:
    def test_delete_existing_dir(self, tmp_root):
        from regian.skills.files import create_directory, delete_directory
        create_directory("te_verwijderen_map")
        result = delete_directory("te_verwijderen_map")
        assert "Succes" in result
        assert not (tmp_root / "te_verwijderen_map").exists()

    def test_delete_nonexistent_dir(self, tmp_root):
        from regian.skills.files import delete_directory
        result = delete_directory("bestaat_niet_map")
        assert "Fout" in result

    def test_delete_dir_with_contents(self, tmp_root):
        from regian.skills.files import write_file, delete_directory
        write_file("mapje/bestand.txt", "inhoud")
        result = delete_directory("mapje")
        assert "Succes" in result
        assert not (tmp_root / "mapje").exists()


# ── rename_file ────────────────────────────────────────────────────────────────

class TestRenameFile:
    def test_rename_existing_file(self, tmp_root):
        from regian.skills.files import write_file, rename_file, read_file
        write_file("oud.txt", "data")
        result = rename_file("oud.txt", "nieuw.txt")
        assert "Succes" in result
        assert not (tmp_root / "oud.txt").exists()
        assert (tmp_root / "nieuw.txt").exists()
        assert read_file("nieuw.txt") == "data"

    def test_rename_nonexistent(self, tmp_root):
        from regian.skills.files import rename_file
        result = rename_file("bestaat_niet.txt", "nieuw.txt")
        assert "Fout" in result


# ── move_file ──────────────────────────────────────────────────────────────────

class TestMoveFile:
    def test_move_to_subdir(self, tmp_root):
        from regian.skills.files import write_file, move_file
        write_file("bron.txt", "inhoud")
        result = move_file("bron.txt", "doel/bron.txt")
        assert "Succes" in result
        assert not (tmp_root / "bron.txt").exists()
        assert (tmp_root / "doel" / "bron.txt").exists()

    def test_move_nonexistent(self, tmp_root):
        from regian.skills.files import move_file
        result = move_file("bestaat_niet.txt", "doel.txt")
        assert "Fout" in result


# ── copy_file ──────────────────────────────────────────────────────────────────

class TestCopyFile:
    def test_copy_file(self, tmp_root):
        from regian.skills.files import write_file, copy_file, read_file
        write_file("origineel.txt", "kopieerbaar")
        result = copy_file("origineel.txt", "kopie.txt")
        assert "Succes" in result
        assert (tmp_root / "origineel.txt").exists()   # origineel blijft
        assert read_file("kopie.txt") == "kopieerbaar"
