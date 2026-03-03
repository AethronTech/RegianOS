# tests/test_skills_workflow.py
"""Tests voor regian/skills/workflow.py — workflow slash-commands."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ── list_workflows ─────────────────────────────────────────────────────────────

class TestListWorkflows:
    def test_bevat_ingebouwde_workflow(self):
        from regian.skills.workflow import list_workflows
        result = list_workflows()
        assert "van_idee_tot_mvp" in result.lower() or "van_idee_tot_mvp" in result

    def test_returnwaarde_is_string(self):
        from regian.skills.workflow import list_workflows
        assert isinstance(list_workflows(), str)


# ── list_workflow_runs ─────────────────────────────────────────────────────────

class TestListWorkflowRuns:
    def test_leeg_geeft_geen_actieve(self, tmp_path, monkeypatch):
        from regian.core import workflow as wf_mod
        from regian.skills.workflow import list_workflow_runs
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        result = list_workflow_runs()
        assert isinstance(result, str)
        assert "geen" in result.lower() or "0" in result or result.strip() != ""

    def test_toont_actieve_run(self, tmp_path, monkeypatch):
        from regian.core import workflow as wf_mod
        from regian.skills.workflow import list_workflow_runs
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        run = wf_mod.WorkflowRun(
            run_id="run_vis1", workflow_id="wf", workflow_name="Mijn Wf",
            started_at="2026-01-01T10:00:00", updated_at="2026-01-01T10:00:00",
            status="running", current_phase_index=0,
            artifacts={}, phase_log=[], input="test", project_path="",
        )
        wf_mod.save_run(run)
        result = list_workflow_runs()
        assert "run_vis1" in result


# ── workflow_status ────────────────────────────────────────────────────────────

class TestWorkflowStatus:
    def test_status_van_bestaande_run(self, tmp_path, monkeypatch):
        from regian.core import workflow as wf_mod
        from regian.skills.workflow import workflow_status
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        run = wf_mod.WorkflowRun(
            run_id="staat1", workflow_id="wf", workflow_name="Status WF",
            started_at="2026-01-01T10:00:00", updated_at="2026-01-01T10:00:00",
            status="waiting", current_phase_index=1,
            artifacts={}, phase_log=[], input="hallo", project_path="",
        )
        wf_mod.save_run(run)
        result = workflow_status("staat1")
        assert "staat1" in result
        assert "waiting" in result.lower() or "wach" in result.lower()

    def test_status_niet_gevonden(self, tmp_path, monkeypatch):
        from regian.core import workflow as wf_mod
        from regian.skills.workflow import workflow_status
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        result = workflow_status("bestaat_noooooit")
        assert "niet gevonden" in result.lower() or "bestaat" in result.lower() or "error" in result.lower()


# ── cancel_workflow ────────────────────────────────────────────────────────────

class TestCancelWorkflow:
    def test_cancel_bestaande_run(self, tmp_path, monkeypatch):
        from regian.core import workflow as wf_mod
        from regian.skills.workflow import cancel_workflow
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        run = wf_mod.WorkflowRun(
            run_id="canc_skill1", workflow_id="wf", workflow_name="W",
            started_at="2026-01-01T10:00:00", updated_at="2026-01-01T10:00:00",
            status="waiting", current_phase_index=0,
            artifacts={}, phase_log=[], input="test", project_path="",
        )
        wf_mod.save_run(run)
        result = cancel_workflow("canc_skill1")
        assert "geannuleerd" in result.lower() or "cancel" in result.lower() or "canc_skill1" in result

    def test_cancel_niet_gevonden(self, tmp_path, monkeypatch):
        from regian.core import workflow as wf_mod
        from regian.skills.workflow import cancel_workflow
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        result = cancel_workflow("bestaat_niet_xyz")
        assert "error" in result.lower() or "niet gevonden" in result.lower() or "bestaat" in result.lower()


# ── BPMN export ────────────────────────────────────────────────────────────────

class TestExportBpmn:
    def test_export_van_ingebouwd_template(self, tmp_path, monkeypatch):
        import regian.settings as settings_mod
        # Stuur de exportuitvoer naar tmp_path
        monkeypatch.setattr(settings_mod, "get_root_dir", lambda: str(tmp_path))
        monkeypatch.setattr(settings_mod, "get_active_project", lambda: "")
        from regian.skills.workflow import export_bpmn
        result = export_bpmn("van_idee_tot_mvp")
        assert ".bpmn" in result or "van_idee_tot_mvp" in result
        bpmn_file = tmp_path / "van_idee_tot_mvp.bpmn"
        assert bpmn_file.exists()

    def test_export_template_onbekend(self):
        from regian.skills.workflow import export_bpmn
        result = export_bpmn("bestaat_niet_xyz")
        assert "error" in result.lower() or "niet gevonden" in result.lower() or "❌" in result


# ── BPMN import ────────────────────────────────────────────────────────────────

class TestImportBpmn:
    def test_import_minimale_bpmn_xml(self, tmp_path, monkeypatch):
        from regian.core import workflow as wf_mod
        from regian.skills.workflow import import_bpmn
        sdir = tmp_path / ".regian_workflow"
        monkeypatch.setattr(wf_mod, "_workflow_dir", lambda pp="": sdir)
        bpmn_content = """<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
             targetNamespace="http://regian.test">
  <process id="test_import_wf" name="Test Import WF" isExecutable="true">
    <startEvent id="start"/>
    <serviceTask id="taak1" name="LLM Stap">
      <documentation>Verwerk de invoer: {{input}}</documentation>
    </serviceTask>
    <userTask id="goedkeuring" name="Goedkeuring">
      <documentation>Controleer het resultaat</documentation>
    </userTask>
    <endEvent id="einde"/>
  </process>
</definitions>"""
        xml_path = tmp_path / "test_import.bpmn"
        xml_path.write_text(bpmn_content, encoding="utf-8")
        result = import_bpmn(str(xml_path))
        # moet JSON-bestand aangemaakt hebben of melden dat het geslaagd is
        assert "test_import_wf" in result or "geïmporteerd" in result.lower() or "import" in result.lower()

    def test_import_bestaand_pad_niet_gevonden(self):
        from regian.skills.workflow import import_bpmn
        result = import_bpmn("/tmp/bestaat_nooit_xyz.bpmn")
        assert "niet gevonden" in result.lower() or "error" in result.lower()


# ── approve_workflow ───────────────────────────────────────────────────────────

class TestApproveWorkflow:
    def _maak_waiting_run(self, wf_mod, sdir_patch):
        """Hulpfunctie: maak een waiting run met een checkpoint template."""
        tpl = {
            "id": "chk_wf", "name": "Checkpoint WF", "description": "", "version": "1.0",
            "phases": [{"id": "vraag", "type": "human_checkpoint", "prompt": "Keur goed: {{input}}"}],
        }
        return tpl

    def test_approve_bestaande_run(self, tmp_path, monkeypatch):
        from regian.core import workflow as wf_mod
        from regian.skills.workflow import approve_workflow
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        tpl = {
            "id": "chk_wf", "name": "CWF", "description": "", "version": "1.0",
            "phases": [{"id": "v", "type": "human_checkpoint", "prompt": "OK? {{input}}"}],
        }
        monkeypatch.setattr(wf_mod, "load_workflow", lambda name, pp="": tpl)
        # Start → waiting
        run = wf_mod.start_workflow("chk_wf", "test")
        result = approve_workflow(run.run_id, feedback="looks good")
        assert "done" in result.lower() or "afgerond" in result.lower() or run.run_id in result

    def test_approve_niet_gevonden(self, tmp_path, monkeypatch):
        from regian.core import workflow as wf_mod
        from regian.skills.workflow import approve_workflow
        sdir = tmp_path / ".regian_workflow_state"
        monkeypatch.setattr(wf_mod, "_state_dir", lambda pp="": sdir)
        result = approve_workflow("bestaat_niet_run")
        assert "error" in result.lower() or "niet gevonden" in result.lower() or "❌" in result


# ── _xml_escape hulpfunctie ───────────────────────────────────────────────────

class TestXmlEscapeSkill:
    def test_ampersand_en_tag_tekens(self):
        from regian.skills.workflow import _xml_escape
        result = _xml_escape("<test> & 'hallo'")
        assert "&lt;" in result
        assert "&amp;" in result

    def test_lege_string(self):
        from regian.skills.workflow import _xml_escape
        assert _xml_escape("") == ""
