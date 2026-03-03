# tests/test_core_workflow.py
"""Tests voor regian/core/workflow.py — workflow-engine."""
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def wf_dir(tmp_path):
    """Tijdelijke workflow-template-map + eenvoudig testtemplate."""
    wdir = tmp_path / ".regian_workflow"
    wdir.mkdir()
    template = {
        "id": "test_wf",
        "name": "Test Workflow",
        "description": "Testdoeleinden",
        "version": "1.0",
        "phases": [
            {
                "id": "stap1",
                "name": "Stap 1",
                "type": "llm_prompt",
                "prompt_template": "Verwerk: {{input}}",
                "output_key": "stap1_output",
                "require_approval": False,
            },
            {
                "id": "wacht",
                "name": "Goedkeuring",
                "type": "human_checkpoint",
                "prompt": "Keur goed: {{stap1_output}}",
            },
            {
                "id": "stap3",
                "name": "Stap 3",
                "type": "llm_prompt",
                "prompt_template": "Afronden: {{stap1_output}}",
                "output_key": "stap3_output",
                "require_approval": False,
            },
        ],
    }
    (wdir / "test_wf.json").write_text(json.dumps(template), encoding="utf-8")
    return wdir


@pytest.fixture
def state_dir(tmp_path):
    """Tijdelijke state-map."""
    sdir = tmp_path / ".regian_workflow_state"
    sdir.mkdir()
    return sdir


# ── WorkflowRun dataklasse ────────────────────────────────────────────────────

class TestWorkflowRun:
    def test_roundtrip_serialisatie(self):
        from regian.core.workflow import WorkflowRun
        run = WorkflowRun(
            run_id="abc123",
            workflow_id="test_wf",
            workflow_name="Test",
            started_at="2026-03-03T10:00:00",
            updated_at="2026-03-03T10:01:00",
            status="running",
            current_phase_index=0,
            artifacts={"input": "hallo"},
            phase_log=[],
            input="hallo",
            project_path="",
        )
        d = run.to_dict()
        run2 = WorkflowRun.from_dict(d)
        assert run2.run_id == "abc123"
        assert run2.artifacts == {"input": "hallo"}
        assert run2.status == "running"

    def test_from_dict_roundtrip(self):
        from regian.core.workflow import WorkflowRun
        d = {
            "run_id": "x1", "workflow_id": "wf", "workflow_name": "W",
            "started_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00",
            "status": "done", "current_phase_index": 2,
            "artifacts": {"prd": "inhoud"}, "phase_log": [],
            "input": "test", "project_path": "/tmp/proj",
        }
        run = WorkflowRun.from_dict(d)
        assert run.workflow_name == "W"
        assert run.artifacts["prd"] == "inhoud"


# ── Template laden ────────────────────────────────────────────────────────────

class TestLoadWorkflow:
    def test_laad_uit_project_dir(self, tmp_path, monkeypatch):
        from regian.core import workflow as wf_mod
        wdir = tmp_path / ".regian_workflow"
        wdir.mkdir()
        tpl = {"id": "abc", "name": "ABC", "description": "", "phases": []}
        (wdir / "abc.json").write_text(json.dumps(tpl), encoding="utf-8")
        monkeypatch.setattr(wf_mod, "_workflow_dir", lambda pp="": wdir if pp else wdir)
        result = wf_mod.load_workflow("abc", str(tmp_path))
        assert result["id"] == "abc"

    def test_ingebouwde_template_beschikbaar(self):
        from regian.core.workflow import load_workflow
        tpl = load_workflow("van_idee_tot_mvp")
        assert tpl["id"] == "van_idee_tot_mvp"
        assert len(tpl["phases"]) == 5  # architect, breakdown, implement, test_validatie, review

    def test_niet_gevonden_gooit_error(self):
        from regian.core.workflow import load_workflow
        with pytest.raises(FileNotFoundError):
            load_workflow("bestaat_niet_xyz_123")

    def test_list_workflows_bevat_ingebouwd(self):
        from regian.core.workflow import list_workflows
        items = list_workflows()
        ids = [w["id"] for w in items]
        assert "van_idee_tot_mvp" in ids


# ── State persistentie ────────────────────────────────────────────────────────

class TestStatePersistentie:
    def _maak_run(self, project_path=""):
        from regian.core.workflow import WorkflowRun
        return WorkflowRun(
            run_id="test42",
            workflow_id="test_wf",
            workflow_name="Test",
            started_at="2026-03-03T10:00:00",
            updated_at="2026-03-03T10:00:00",
            status="running",
            current_phase_index=0,
            artifacts={"input": "hallo"},
            phase_log=[],
            input="hallo",
            project_path=project_path,
        )

    def test_save_en_load(self, tmp_path, monkeypatch):
        from regian.core import workflow as wf_mod
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        run = self._maak_run()
        wf_mod.save_run(run)
        assert (sdir / "test42.json").exists()
        loaded = wf_mod.load_run("test42")
        assert loaded.run_id == "test42"
        assert loaded.status == "running"

    def test_load_niet_gevonden(self, tmp_path, monkeypatch):
        from regian.core import workflow as wf_mod
        sdir = tmp_path / ".regian_workflow_state"
        sdir.mkdir(parents=True)
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        with pytest.raises(FileNotFoundError):
            wf_mod.load_run("bestaat_niet")

    def test_list_runs_leeg(self, tmp_path, monkeypatch):
        from regian.core import workflow as wf_mod
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        assert wf_mod.list_runs() == []

    def test_list_runs_vindt_opgeslagen(self, tmp_path, monkeypatch):
        from regian.core import workflow as wf_mod
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        run = self._maak_run()
        wf_mod.save_run(run)
        runs = wf_mod.list_runs()
        assert len(runs) == 1
        assert runs[0].run_id == "test42"


# ── Template-substitutie ──────────────────────────────────────────────────────

class TestRenderTemplate:
    def test_variabele_substitutie(self):
        from regian.core.workflow import _render_template
        result = _render_template("Hallo {{naam}}, idee: {{input}}", {"naam": "Regian", "input": "MVP"})
        assert result == "Hallo Regian, idee: MVP"

    def test_onbekende_variabele_blijft_staan(self):
        from regian.core.workflow import _render_template
        result = _render_template("Test {{onbekend}}", {})
        assert "{{onbekend}}" in result

    def test_lege_template(self):
        from regian.core.workflow import _render_template
        assert _render_template("", {"input": "x"}) == ""

    def test_geen_placeholders(self):
        from regian.core.workflow import _render_template
        assert _render_template("Gewone tekst", {"x": "y"}) == "Gewone tekst"


# ── Human checkpoint fase ─────────────────────────────────────────────────────

class TestHumanCheckpoint:
    def test_geeft_needs_approval_true(self):
        from regian.core.workflow import execute_phase, WorkflowRun
        run = WorkflowRun(
            run_id="r1", workflow_id="wf", workflow_name="W",
            started_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
            status="running", current_phase_index=0,
            artifacts={"input": "test"}, phase_log=[], input="test", project_path="",
        )
        phase = {"id": "check", "type": "human_checkpoint", "prompt": "Controleer: {{input}}"}
        output, needs_approval = execute_phase(run, phase)
        assert needs_approval is True
        assert "test" in output

    def test_onbekend_fase_type(self):
        from regian.core.workflow import execute_phase, WorkflowRun
        run = WorkflowRun(
            run_id="r2", workflow_id="wf", workflow_name="W",
            started_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
            status="running", current_phase_index=0,
            artifacts={}, phase_log=[], input="test", project_path="",
        )
        phase = {"id": "onbekend", "type": "bestaat_niet"}
        output, needs_approval = execute_phase(run, phase)
        assert "Onbekend" in output
        assert needs_approval is False


# ── Tool chain fase ────────────────────────────────────────────────────────────

class TestToolChain:
    def test_tool_chain_roept_registry_aan(self, tmp_root):
        from regian.core.workflow import _run_tool_chain, WorkflowRun
        run = WorkflowRun(
            run_id="r3", workflow_id="wf", workflow_name="W",
            started_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
            status="running", current_phase_index=0,
            artifacts={"naam": "testbestand.txt"}, phase_log=[], input="", project_path="",
        )
        phase = {
            "type": "tool_chain",
            "steps": [
                {"tool": "write_file", "args": {"path": "tc_test.txt", "content": "hoi"}},
            ],
        }
        result = _run_tool_chain(phase, run.artifacts, run)
        assert "write_file" in result
        assert "Succes" in result or "tc_test.txt" in result

    def test_tool_chain_leeg(self):
        from regian.core.workflow import _run_tool_chain, WorkflowRun
        run = WorkflowRun(
            run_id="r4", workflow_id="wf", workflow_name="W",
            started_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
            status="running", current_phase_index=0,
            artifacts={}, phase_log=[], input="", project_path="",
        )
        result = _run_tool_chain({"type": "tool_chain", "steps": []}, {}, run)
        assert "Geen stappen" in result


# ── _advance en start_workflow ────────────────────────────────────────────────

class TestAdvanceFlow:
    """Test de _advance-loop met templates die geen LLM nodig hebben."""

    def _checkpoint_template(self) -> dict:
        return {
            "id": "chk_wf",
            "name": "Checkpoint WF",
            "description": "Testworkflow met directe checkpoint",
            "version": "1.0",
            "phases": [
                {
                    "id": "vraag",
                    "name": "Bevestig idee",
                    "type": "human_checkpoint",
                    "prompt": "Keur goed: {{input}}",
                },
            ],
        }

    def _two_phase_template(self) -> dict:
        return {
            "id": "two_phase",
            "name": "Twee fasen",
            "description": "Twee fasen: LLM dan checkpoint",
            "version": "1.0",
            "phases": [
                {
                    "id": "stap1",
                    "name": "LLM stap",
                    "type": "llm_prompt",
                    "prompt_template": "Verwerk: {{input}}",
                    "output_key": "stap1_output",
                    "require_approval": False,
                },
                {
                    "id": "check",
                    "name": "Goedkeuring",
                    "type": "human_checkpoint",
                    "prompt": "Controleer: {{stap1_output}}",
                },
            ],
        }

    def test_start_workflow_human_checkpoint_direct_waiting(self, tmp_path, monkeypatch):
        """Workflow met human_checkpoint als eerste fase gaat direct naar waiting."""
        from regian.core import workflow as wf_mod
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        tpl = self._checkpoint_template()
        monkeypatch.setattr(wf_mod, "load_workflow", lambda name, pp="": tpl)
        run = wf_mod.start_workflow("chk_wf", "mijn idee")
        assert run.status == "waiting"
        assert run.current_phase_index == 0
        assert "mijn idee" in run.artifacts.get("input", "")

    def test_advance_na_checkpoint(self, tmp_path, monkeypatch):
        """advance_run gaat na een human_checkpoint naar de volgende fase (done als geen meer)."""
        from regian.core import workflow as wf_mod
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        tpl = self._checkpoint_template()
        monkeypatch.setattr(wf_mod, "load_workflow", lambda name, pp="": tpl)
        # Start → waiting
        run = wf_mod.start_workflow("chk_wf", "idee")
        assert run.status == "waiting"
        # Advance → done (maar checkpoint is index 0, enige fase)
        done = wf_mod.advance_run(run.run_id)
        assert done.status == "done"

    def test_advance_feedback_wordt_opgeslagen(self, tmp_path, monkeypatch):
        """Feedback bij advance_run wordt als artifact opgeslagen."""
        from regian.core import workflow as wf_mod
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        tpl = self._checkpoint_template()
        monkeypatch.setattr(wf_mod, "load_workflow", lambda name, pp="": tpl)
        run = wf_mod.start_workflow("chk_wf", "idee")
        done = wf_mod.advance_run(run.run_id, user_feedback="ziet er goed uit!")
        assert "ziet er goed uit!" in str(done.artifacts.values())

    def test_advance_met_llm_fase_en_checkpoint(self, tmp_path, monkeypatch):
        """Twee-fase workflow: LLM → checkpoint. Na advance_run wordt status done."""
        from regian.core import workflow as wf_mod
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        tpl = self._two_phase_template()
        monkeypatch.setattr(wf_mod, "load_workflow", lambda name, pp="": tpl)

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "LLM-resultaat"
        mock_llm.invoke.return_value = mock_response

        with patch("regian.core.workflow._get_llm", return_value=mock_llm):
            run = wf_mod.start_workflow("two_phase", "begin")
        # LLM fase heeft require_approval=False → doorgaan tot human_checkpoint → waiting
        assert run.status == "waiting"
        assert run.artifacts.get("stap1_output") == "LLM-resultaat"

        # Advance van checkpoint → done
        with patch("regian.core.workflow._get_llm", return_value=mock_llm):
            done = wf_mod.advance_run(run.run_id)
        assert done.status == "done"

    def test_advance_fase_met_error_zet_status_error(self, tmp_path, monkeypatch):
        """Als een fase een exception gooit, zet _advance status op error."""
        from regian.core import workflow as wf_mod
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        tpl = {
            "id": "err_wf", "name": "Error WF", "description": "", "version": "1.0",
            "phases": [{"id": "stap1", "type": "llm_prompt",
                        "prompt_template": "Test", "output_key": "x",
                        "require_approval": False}],
        }
        monkeypatch.setattr(wf_mod, "load_workflow", lambda name, pp="": tpl)

        def _kapotte_llm():
            raise RuntimeError("LLM kapot")

        with patch("regian.core.workflow._get_llm", side_effect=_kapotte_llm):
            run = wf_mod.start_workflow("err_wf", "test")
        assert run.status == "error"

    def test_list_workflows_met_project_dir(self, tmp_path, monkeypatch):
        """list_workflows vindt ook templates in de project-map."""
        from regian.core import workflow as wf_mod
        wdir = tmp_path / ".regian_workflow"
        wdir.mkdir()
        tpl = {"id": "proj_wf", "name": "Proj WF", "description": "test", "phases": []}
        (wdir / "proj_wf.json").write_text(json.dumps(tpl), encoding="utf-8")
        monkeypatch.setattr(wf_mod, "_workflow_dir", lambda pp="": wdir)
        items = wf_mod.list_workflows(str(tmp_path))
        ids = [w["id"] for w in items]
        assert "proj_wf" in ids


# ── Cancel run ────────────────────────────────────────────────────────────────

class TestCancelRun:
    def test_cancel_zet_status_cancelled(self, tmp_path, monkeypatch):
        from regian.core import workflow as wf_mod
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        run = wf_mod.WorkflowRun(
            run_id="canc1", workflow_id="wf", workflow_name="W",
            started_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
            status="waiting", current_phase_index=1,
            artifacts={}, phase_log=[], input="test", project_path="",
        )
        wf_mod.save_run(run)
        cancelled = wf_mod.cancel_run("canc1")
        assert cancelled.status == "cancelled"
        loaded = wf_mod.load_run("canc1")
        assert loaded.status == "cancelled"

    def test_advance_niet_waiting_gooit_valueerror(self, tmp_path, monkeypatch):
        from regian.core import workflow as wf_mod
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        run = wf_mod.WorkflowRun(
            run_id="adv1", workflow_id="wf", workflow_name="W",
            started_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
            status="done", current_phase_index=3,
            artifacts={}, phase_log=[], input="test", project_path="",
        )
        wf_mod.save_run(run)
        with pytest.raises(ValueError, match="waiting"):
            wf_mod.advance_run("adv1")


# ── XML escaping voor BPMN export ─────────────────────────────────────────────

class TestXmlEscape:
    def test_escaping(self):
        from regian.skills.workflow import _xml_escape
        assert _xml_escape("a & b < c > d \"e\"") == "a &amp; b &lt; c &gt; d &quot;e&quot;"

    def test_geen_speciale_tekens(self):
        from regian.skills.workflow import _xml_escape
        assert _xml_escape("gewone tekst") == "gewone tekst"
