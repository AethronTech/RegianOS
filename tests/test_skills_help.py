# tests/test_skills_help.py
"""Tests voor regian/skills/help.py — get_help functie."""
import pytest


class TestGetHelp:
    def test_returns_string(self):
        from regian.skills.help import get_help
        result = get_help()
        assert isinstance(result, str)

    def test_contains_skill_header(self):
        from regian.skills.help import get_help
        result = get_help()
        # Verwacht minstens één skill-module naam
        assert "##" in result or "skills" in result.lower()

    def test_filter_on_existing_module(self):
        from regian.skills.help import get_help
        result = get_help("files")
        assert "write_file" in result or "files" in result.lower()

    def test_filter_on_nonexistent_returns_minimal(self):
        from regian.skills.help import get_help
        result = get_help("bestaat_absoluut_niet_xyz")
        assert isinstance(result, str)
        # Geen matches = enkel de header
        assert "write_file" not in result

    def test_contains_function_names(self):
        from regian.skills.help import get_help
        result = get_help()
        # Verwacht enkele bekende functies
        assert "run_shell" in result or "write_file" in result

    def test_contains_docstrings(self):
        from regian.skills.help import get_help
        result = get_help("terminal")
        # Docstring van run_shell
        assert "shell" in result.lower() or "commando" in result.lower()

    def test_help_terminal_filter(self):
        from regian.skills.help import get_help
        result = get_help("terminal")
        assert "run_shell" in result or "run_python" in result

    def test_help_cron_filter(self):
        from regian.skills.help import get_help
        result = get_help("cron")
        assert "schedule" in result.lower() or "cron" in result.lower()
