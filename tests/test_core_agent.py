# tests/test_core_agent.py
"""Tests voor regian/core/agent.py — SkillRegistry (zonder LLM)."""
import pytest
from unittest.mock import patch, MagicMock


# ── SkillRegistry ──────────────────────────────────────────────────────────────

class TestSkillRegistry:
    def test_registry_loads_tools(self):
        from regian.core.agent import registry
        assert len(registry.tools) > 0

    def test_registry_contains_known_skills(self):
        from regian.core.agent import registry
        names = {t.name for t in registry.tools}
        # Verwacht minstens enkele bekende skills
        assert "write_file" in names
        assert "run_shell" in names
        assert "get_help" in names

    def test_no_private_functions_registered(self):
        from regian.core.agent import registry
        names = {t.name for t in registry.tools}
        for name in names:
            assert not name.startswith("_"), f"Privéfunctie '{name}' mag niet in registry"

    def test_tool_map_keys_match_tools(self):
        from regian.core.agent import registry
        tool_names = {t.name for t in registry.tools}
        map_keys = set(registry.tool_map.keys())
        assert tool_names == map_keys

    def test_call_unknown_skill(self):
        from regian.core.agent import registry
        result = registry.call("bestaat_niet_skill_xyz", {})
        assert "❌" in result or "Onbekende" in result

    def test_call_write_file(self, tmp_root):
        from regian.core.agent import registry
        result = registry.call("write_file", {"path": "agent_test.txt", "content": "via registry"})
        assert "Succes" in result
        assert (tmp_root / "agent_test.txt").exists()

    def test_call_by_string_json_args(self, tmp_root):
        from regian.core.agent import registry
        import json
        args_str = json.dumps({"path": "via_string.txt", "content": "inhoud"})
        result = registry.call_by_string("write_file", args_str)
        assert "Succes" in result

    def test_call_by_string_positional(self, tmp_root):
        from regian.core.agent import registry
        # read_file met gewone string als arg
        (tmp_root / "testlees.txt").write_text("inhoud", encoding="utf-8")
        result = registry.call_by_string("read_file", "testlees.txt")
        assert "inhoud" in result

    def test_call_by_string_unknown(self):
        from regian.core.agent import registry
        result = registry.call_by_string("bestaat_niet_xyz", "")
        assert "❌" in result

    def test_list_commands_returns_all_skills(self):
        from regian.core.agent import registry
        result = registry.list_commands()
        assert "write_file" in result
        assert "run_shell" in result

    def test_skill_modules_returns_list(self):
        from regian.core.agent import registry
        modules = registry.skill_modules()
        assert isinstance(modules, list)
        assert "files" in modules
        assert "terminal" in modules

    def test_reload_increases_or_keeps_count(self):
        from regian.core.agent import registry
        count_before = len(registry.tools)
        registry.reload()
        count_after = len(registry.tools)
        # Na reload moeten minstens evenveel skills beschikbaar zijn
        assert count_after >= count_before


# ── CONFIRM_REQUIRED ────────────────────────────────────────────────────────────

class TestConfirmRequired:
    def test_returns_set(self, monkeypatch):
        monkeypatch.setenv("CONFIRM_REQUIRED", "delete_file,repo_delete")
        from regian.core.agent import CONFIRM_REQUIRED
        result = CONFIRM_REQUIRED()
        assert isinstance(result, set)
        assert "delete_file" in result

    def test_live_reload_from_env(self, monkeypatch):
        """CONFIRM_REQUIRED leest altijd de actuele waarde."""
        monkeypatch.setenv("CONFIRM_REQUIRED", "skill_a,skill_b")
        from regian.core.agent import CONFIRM_REQUIRED
        result1 = CONFIRM_REQUIRED()
        monkeypatch.setenv("CONFIRM_REQUIRED", "skill_c")
        result2 = CONFIRM_REQUIRED()
        assert "skill_a" in result1
        assert "skill_c" in result2
        assert "skill_a" not in result2
