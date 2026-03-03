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


# ── OrchestratorAgent ──────────────────────────────────────────────────────────

class TestOrchestratorAgent:
    """Tests voor OrchestratorAgent zonder echte LLM-aanroepen."""

    @pytest.fixture
    def mock_llm(self):
        """Eenvoudige mock die een JSON plan teruggeeft."""
        from unittest.mock import MagicMock
        llm = MagicMock()
        return llm

    @pytest.fixture
    def agent(self, mock_llm):
        from regian.core.agent import OrchestratorAgent
        orch = OrchestratorAgent.__new__(OrchestratorAgent)
        orch.tools = []
        orch.base_llm = mock_llm
        return orch, mock_llm

    def test_execute_plan_returns_results(self, agent, tmp_root):
        orch, _ = agent
        plan = [
            {"tool": "write_file", "args": {"path": "plan_test.txt", "content": "hallo"}},
        ]
        result = orch.execute_plan(plan)
        assert "write_file" in result
        assert "✅" in result

    def test_execute_plan_empty_returns_message(self, agent):
        orch, _ = agent
        result = orch.execute_plan([])
        assert "Geen" in result

    def test_execute_plan_unknown_tool(self, agent):
        orch, _ = agent
        plan = [{"tool": "bestaat_niet_xyz", "args": {}}]
        result = orch.execute_plan(plan)
        assert "❌" in result or "bestaat_niet_xyz" in result

    def test_execute_plan_passes_group_id_to_log(self, agent, tmp_root, tmp_path, monkeypatch):
        import regian.core.action_log as al
        log_file = tmp_path / "test.jsonl"
        monkeypatch.setattr(al, "_get_log_file", lambda: log_file)
        orch, _ = agent
        plan = [{"tool": "write_file", "args": {"path": "gid_test.txt", "content": "x"}}]
        orch.execute_plan(plan, source="chat", group_id="testgid")
        import json
        lines = [l for l in log_file.read_text().splitlines() if l.strip()]
        assert any(json.loads(l).get("group_id") == "testgid" for l in lines)

    def test_plan_parses_valid_json(self, agent):
        import json
        orch, mock_llm = agent
        plan_data = [{"tool": "run_shell", "args": {"command": "ls"}}]
        mock_llm.invoke.return_value.content = json.dumps(plan_data)
        result = orch.plan("doe iets")
        assert result == plan_data

    def test_plan_strips_markdown_fences(self, agent):
        orch, mock_llm = agent
        mock_llm.invoke.return_value.content = "```json\n[]\n```"
        result = orch.plan("niets")
        assert result == []

    def test_plan_returns_empty_on_invalid_json(self, agent):
        orch, mock_llm = agent
        mock_llm.invoke.return_value.content = "dit is geen json"
        result = orch.plan("iets")
        assert result == []

    def test_plan_returns_empty_on_non_list_json(self, agent):
        orch, mock_llm = agent
        mock_llm.invoke.return_value.content = '{"tool": "foo"}'
        result = orch.plan("iets")
        assert result == []

    def test_plan_handles_list_content(self, agent):
        orch, mock_llm = agent
        mock_llm.invoke.return_value.content = ["[", "]"]
        result = orch.plan("iets")
        assert result == []

    def test_run_with_plan_executes(self, agent, tmp_root):
        import json
        orch, mock_llm = agent
        plan_data = [{"tool": "write_file", "args": {"path": "run_test.txt", "content": "via run"}}]
        mock_llm.invoke.return_value.content = json.dumps(plan_data)
        result = orch.run("schrijf bestand")
        assert "write_file" in result or "run_test" in result or "✅" in result

    def test_run_without_plan_uses_llm(self, agent):
        orch, mock_llm = agent
        # Eerste invoke = planner (geeft leeg plan), tweede invoke = chat fallback
        from unittest.mock import MagicMock
        resp_plan = MagicMock()
        resp_plan.content = "[]"
        resp_chat = MagicMock()
        resp_chat.content = "Hallo!"
        mock_llm.invoke.side_effect = [resp_plan, resp_chat]
        result = orch.run("zeg hallo")
        assert result == "Hallo!"

    def test_run_catches_exception(self, agent):
        orch, mock_llm = agent
        mock_llm.invoke.side_effect = Exception("LLM kapot")
        result = orch.run("iets")
        assert "Fout" in result or "kapot" in result

    def test_tool_catalog_is_string(self):
        from regian.core.agent import OrchestratorAgent
        with patch("regian.core.agent.ChatGoogleGenerativeAI"), \
             patch("regian.core.agent.ChatOllama"):
            orch = OrchestratorAgent()
        catalog = orch._tool_catalog()
        assert isinstance(catalog, str)
        assert len(catalog) > 0


# ── _project_context_block ─────────────────────────────────────────────────────

class TestProjectContextBlock:
    """Tests voor _project_context_block — inclusief de nieuwe src/-instructie."""

    def _block(self, ctx):
        from regian.core.agent import _project_context_block
        return _project_context_block(ctx)

    def test_returns_empty_for_none(self):
        assert self._block(None) == ""

    def test_contains_project_name(self):
        ctx = {"name": "MijnProject", "type": "python", "path": "/workspace/mijn"}
        result = self._block(ctx)
        assert "MijnProject" in result

    def test_contains_path(self):
        ctx = {"name": "P", "type": "node", "path": "/workspace/p"}
        result = self._block(ctx)
        assert "/workspace/p" in result

    def test_software_type_shows_src_hint(self):
        for ptype in ("python", "node", "typescript", "javascript", "react", "vue",
                      "web", "flutter", "rust", "go", "java", "kotlin", "swift"):
            ctx = {"name": "P", "type": ptype, "path": "/workspace/p"}
            result = self._block(ctx)
            assert "src/" in result, f"type '{ptype}' moet src/ hint tonen"

    def test_non_software_type_no_src_hint(self):
        ctx = {"name": "P", "type": "data", "path": "/workspace/p"}
        result = self._block(ctx)
        assert "src/" not in result

    def test_contains_git_repo_if_present(self):
        ctx = {"name": "P", "type": "python", "path": "/w", "git_repo": "git@github.com:x/y"}
        result = self._block(ctx)
        assert "git@github.com:x/y" in result

    def test_git_repo_absent_if_not_set(self):
        ctx = {"name": "P", "type": "python", "path": "/w"}
        result = self._block(ctx)
        assert "Repo:" not in result

    def test_contains_description_if_present(self):
        ctx = {"name": "P", "type": "python", "path": "/w", "description": "Een testproject"}
        result = self._block(ctx)
        assert "Een testproject" in result

    def test_always_contains_path_warning(self):
        ctx = {"name": "P", "type": "docs", "path": "/workspace/docs"}
        result = self._block(ctx)
        assert "/workspace/docs/" in result
        assert "ALTIJD" in result


# ── _get_project_context ───────────────────────────────────────────────────────

class TestGetProjectContext:
    def test_returns_none_when_no_active_project(self, monkeypatch):
        import regian.core.agent as ag
        monkeypatch.setattr("regian.core.agent.get_active_project", lambda: None)
        result = ag._get_project_context()
        assert result is None

    def test_returns_none_when_manifest_not_found(self, monkeypatch):
        import regian.core.agent as ag
        monkeypatch.setattr("regian.core.agent.get_active_project", lambda: "bestaat_niet_xyz")
        result = ag._get_project_context()
        assert result is None


# ── tools_for_project ──────────────────────────────────────────────────────────

class TestToolsForProject:
    def test_returns_all_tools_for_none_type(self):
        from regian.core.agent import registry
        result = registry.tools_for_project(project_type=None)
        assert len(result) > 0

    def test_returns_all_tools_for_all_type(self):
        from regian.core.agent import registry
        result = registry.tools_for_project(project_type="all")
        assert len(result) == len(registry.tools)

    def test_allowed_tools_filters_by_module(self):
        from regian.core.agent import registry
        result = registry.tools_for_project(allowed_tools=["files"])
        for t in result:
            func = registry._functions.get(t.name)
            assert func is not None
            assert func.__module__.split(".")[-1] == "files"

    def test_docs_type_returns_subset(self):
        from regian.core.agent import registry, _TOOLS_BY_TYPE
        result = registry.tools_for_project(project_type="docs")
        # Als docs een beperkte set heeft, mag het niet meer zijn dan all
        assert len(result) <= len(registry.tools)

    def test_unknown_type_falls_back_to_all(self):
        from regian.core.agent import registry
        result = registry.tools_for_project(project_type="onbekend_type_xyz")
        assert len(result) == len(registry.tools)
