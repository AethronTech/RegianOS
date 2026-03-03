# tests/test_skills_project.py
"""
Tests voor regian/skills/project.py.
Dekt: create_project, activate_project, deactivate_project,
       get_project_info, list_projects.
"""
import json
import os
import pytest
from pathlib import Path


# ── Fixture ────────────────────────────────────────────────────────────────────

@pytest.fixture
def ws(tmp_root, tmp_env_file, monkeypatch):
    """
    Geeft een lege werkmap terug met een geïsoleerd .env-bestand.
    ACTIVE_PROJECT wordt geleegd zodat tests met een schone lei starten.
    """
    import regian.settings as s
    monkeypatch.setattr(s, "ENV_FILE", tmp_env_file)
    monkeypatch.setenv("ACTIVE_PROJECT", "")
    return tmp_root


# ── Hulpfunctie ────────────────────────────────────────────────────────────────

def _read_manifest(ws: Path, name: str) -> dict:
    return json.loads((ws / name / ".regian_project.json").read_text(encoding="utf-8"))


# ── create_project ─────────────────────────────────────────────────────────────

class TestCreateProject:
    def test_software_project_aanmaken(self, ws):
        from regian.skills.project import create_project
        result = create_project("mijn-app", "software")
        assert "✅" in result
        assert (ws / "mijn-app").is_dir()
        assert (ws / "mijn-app" / "src").is_dir()
        assert (ws / "mijn-app" / "tests").is_dir()
        assert (ws / "mijn-app" / "docs").is_dir()

    def test_docs_project_subdirs(self, ws):
        from regian.skills.project import create_project
        create_project("mijn-docs", "docs")
        assert (ws / "mijn-docs" / "content").is_dir()
        assert (ws / "mijn-docs" / "assets").is_dir()

    def test_data_project_subdirs(self, ws):
        from regian.skills.project import create_project
        create_project("mijn-data", "data")
        assert (ws / "mijn-data" / "data" / "raw").is_dir()
        assert (ws / "mijn-data" / "data" / "processed").is_dir()
        assert (ws / "mijn-data" / "notebooks").is_dir()

    def test_generic_project_geen_submappen(self, ws):
        from regian.skills.project import create_project
        create_project("vrij", "generic")
        assert (ws / "vrij").is_dir()
        subdirs = [d for d in (ws / "vrij").iterdir() if d.is_dir()]
        assert subdirs == []

    def test_manifest_inhoud(self, ws):
        from regian.skills.project import create_project
        create_project("meta", "software", description="Testproject", git_repo="user/repo")
        m = _read_manifest(ws, "meta")
        assert m["name"] == "meta"
        assert m["type"] == "software"
        assert m["description"] == "Testproject"
        assert m["git_repo"] == "user/repo"
        assert m["active"] is False
        assert "created_at" in m

    def test_manifest_type_standaard_software(self, ws):
        from regian.skills.project import create_project
        create_project("default-type")
        m = _read_manifest(ws, "default-type")
        assert m["type"] == "software"

    def test_ongeldig_type_geeft_fout(self, ws):
        from regian.skills.project import create_project
        result = create_project("bad", "onbekend")
        assert "❌" in result
        assert not (ws / "bad").exists()

    def test_lege_naam_geeft_fout(self, ws):
        from regian.skills.project import create_project
        result = create_project("   ")
        assert "❌" in result

    def test_dubbelkloon_geeft_waarschuwing(self, ws):
        from regian.skills.project import create_project
        create_project("dubbel", "generic")
        result = create_project("dubbel", "generic")
        assert "⚠️" in result

    def test_spaties_in_naam_worden_underscores(self, ws):
        from regian.skills.project import create_project
        result = create_project("mijn project")
        assert "mijn_project" in result
        assert (ws / "mijn_project").is_dir()

    def test_type_case_insensitive(self, ws):
        from regian.skills.project import create_project
        result = create_project("upper", "SOFTWARE")
        assert "✅" in result
        m = _read_manifest(ws, "upper")
        assert m["type"] == "software"


# ── activate_project ───────────────────────────────────────────────────────────

class TestActivateProject:
    def test_activeert_manifest_vlag(self, ws):
        from regian.skills.project import create_project, activate_project
        create_project("proj-a", "software")
        result = activate_project("proj-a")
        assert "✅" in result
        m = _read_manifest(ws, "proj-a")
        assert m["active"] is True

    def test_activeert_env_variabele(self, ws):
        from regian.skills.project import create_project, activate_project
        create_project("proj-b", "generic")
        activate_project("proj-b")
        assert os.environ.get("ACTIVE_PROJECT") == "proj-b"

    def test_deactiveert_vorig_project(self, ws):
        from regian.skills.project import create_project, activate_project
        create_project("proj-oud", "software")
        create_project("proj-nieuw", "software")
        activate_project("proj-oud")
        activate_project("proj-nieuw")
        assert _read_manifest(ws, "proj-oud")["active"] is False
        assert _read_manifest(ws, "proj-nieuw")["active"] is True

    def test_niet_bestaand_project_geeft_fout(self, ws):
        from regian.skills.project import activate_project
        result = activate_project("bestaat-niet")
        assert "❌" in result

    def test_activeren_zelfde_project_twee_keer(self, ws):
        """Dubbel activeren mag niet crashen."""
        from regian.skills.project import create_project, activate_project
        create_project("idem", "generic")
        activate_project("idem")
        result = activate_project("idem")
        assert "✅" in result
        assert _read_manifest(ws, "idem")["active"] is True


# ── deactivate_project ─────────────────────────────────────────────────────────

class TestDeactivateProject:
    def test_deactiveert_env_variabele(self, ws):
        from regian.skills.project import create_project, activate_project, deactivate_project
        create_project("proj-d", "generic")
        activate_project("proj-d")
        result = deactivate_project()
        assert "✅" in result
        assert os.environ.get("ACTIVE_PROJECT") == ""

    def test_deactiveert_manifest_vlag(self, ws):
        from regian.skills.project import create_project, activate_project, deactivate_project
        create_project("proj-e", "generic")
        activate_project("proj-e")
        deactivate_project()
        assert _read_manifest(ws, "proj-e")["active"] is False

    def test_geen_actief_project_geeft_info(self, ws, monkeypatch):
        from regian.skills.project import deactivate_project
        monkeypatch.setenv("ACTIVE_PROJECT", "")
        result = deactivate_project()
        assert "ℹ️" in result

    def test_deactiveren_zonder_manifest_crasht_niet(self, ws, monkeypatch):
        """Deactiveren wanneer het manifest al verwijderd is."""
        from regian.skills.project import deactivate_project
        monkeypatch.setenv("ACTIVE_PROJECT", "spook-project")
        result = deactivate_project()
        assert "✅" in result


# ── get_project_info ───────────────────────────────────────────────────────────

class TestGetProjectInfo:
    def test_info_via_naam(self, ws):
        from regian.skills.project import create_project, get_project_info
        create_project("info-proj", "docs", description="Test beschrijving")
        result = get_project_info("info-proj")
        assert "info-proj" in result
        assert "docs" in result
        assert "Test beschrijving" in result

    def test_info_via_actief_project(self, ws, monkeypatch):
        from regian.skills.project import create_project, get_project_info
        create_project("actief-proj", "data")
        monkeypatch.setenv("ACTIVE_PROJECT", "actief-proj")
        result = get_project_info()
        assert "actief-proj" in result

    def test_info_geen_naam_geen_actief(self, ws, monkeypatch):
        from regian.skills.project import get_project_info
        monkeypatch.setenv("ACTIVE_PROJECT", "")
        result = get_project_info()
        assert "ℹ️" in result

    def test_niet_bestaand_project_geeft_fout(self, ws):
        from regian.skills.project import get_project_info
        result = get_project_info("bestaat-niet")
        assert "❌" in result

    def test_toont_git_repo(self, ws):
        from regian.skills.project import create_project, get_project_info
        create_project("repo-proj", "software", git_repo="user/repo")
        result = get_project_info("repo-proj")
        assert "user/repo" in result

    def test_actief_vlag_zichtbaar(self, ws, monkeypatch):
        from regian.skills.project import create_project, activate_project, get_project_info
        create_project("vlag-proj", "generic")
        activate_project("vlag-proj")
        result = get_project_info("vlag-proj")
        assert "✅" in result


# ── list_projects ──────────────────────────────────────────────────────────────

class TestListProjects:
    def test_lege_werkmap(self, ws):
        from regian.skills.project import list_projects
        result = list_projects()
        assert "ℹ️" in result

    def test_een_project(self, ws):
        from regian.skills.project import create_project, list_projects
        create_project("enkel", "software", description="Een project")
        result = list_projects()
        assert "enkel" in result
        assert "software" in result

    def test_meerdere_projecten(self, ws):
        from regian.skills.project import create_project, list_projects
        create_project("alpha", "software")
        create_project("beta", "docs")
        result = list_projects()
        assert "alpha" in result
        assert "beta" in result

    def test_actief_project_gemarkeerd(self, ws, monkeypatch):
        from regian.skills.project import create_project, list_projects
        create_project("huidig", "generic")
        monkeypatch.setenv("ACTIVE_PROJECT", "huidig")
        result = list_projects()
        assert "🔵" in result or "actief" in result.lower()

    def test_mappen_zonder_manifest_genegeerd(self, ws):
        from regian.skills.project import create_project, list_projects
        create_project("met-manifest", "generic")
        (ws / "zonder-manifest").mkdir()
        result = list_projects()
        assert "met-manifest" in result
        assert "zonder-manifest" not in result

    def test_toont_type_icoon(self, ws):
        from regian.skills.project import create_project, list_projects
        create_project("icoon-proj", "docs")
        result = list_projects()
        assert "📄" in result  # icoon voor docs-type


# ── rename_project ─────────────────────────────────────────────────────────────

class TestRenameProject:
    def test_basishernoem(self, ws):
        from regian.skills.project import create_project, rename_project
        create_project("oud", "generic")
        result = rename_project("oud", "nieuw")
        assert "✅" in result
        assert (ws / "nieuw").is_dir()
        assert not (ws / "oud").exists()

    def test_manifest_bijgewerkt(self, ws):
        from regian.skills.project import create_project, rename_project
        create_project("proj_a", "software")
        rename_project("proj_a", "proj_b")
        manifest = _read_manifest(ws, "proj_b")
        assert manifest["name"] == "proj_b"
        assert "proj_b" in manifest["path"]
        assert "proj_a" not in manifest["path"]

    def test_actief_project_bijgewerkt(self, ws, monkeypatch):
        import regian.settings as s
        from regian.skills.project import create_project, rename_project
        create_project("actief_oud", "generic")
        monkeypatch.setenv("ACTIVE_PROJECT", "actief_oud")
        monkeypatch.setattr(s, "get_active_project", lambda: "actief_oud")
        captured = {}
        monkeypatch.setattr(s, "set_active_project", lambda n: captured.update({"name": n}))
        rename_project("actief_oud", "actief_nieuw")
        assert captured.get("name") == "actief_nieuw"

    def test_niet_actief_project_ongewijzigd(self, ws, monkeypatch):
        import regian.settings as s
        from regian.skills.project import create_project, rename_project
        create_project("inactief", "generic")
        monkeypatch.setenv("ACTIVE_PROJECT", "ander_project")
        monkeypatch.setattr(s, "get_active_project", lambda: "ander_project")
        captured = {}
        monkeypatch.setattr(s, "set_active_project", lambda n: captured.update({"name": n}))
        rename_project("inactief", "hernoemd")
        assert "name" not in captured  # set_active_project niet aangeroepen

    def test_workflow_state_bijgewerkt(self, ws):
        import json
        from regian.skills.project import create_project, rename_project
        create_project("wf_oud", "generic")
        state_dir = ws / "wf_oud" / ".regian_workflow_state"
        state_dir.mkdir()
        state = {"run_id": "abc", "project_path": str(ws / "wf_oud"), "status": "done"}
        (state_dir / "abc.json").write_text(json.dumps(state), encoding="utf-8")
        rename_project("wf_oud", "wf_nieuw")
        updated = json.loads((ws / "wf_nieuw" / ".regian_workflow_state" / "abc.json")
                             .read_text(encoding="utf-8"))
        assert "wf_nieuw" in updated["project_path"]
        assert "wf_oud" not in updated["project_path"]

    def test_fout_als_oud_niet_bestaat(self, ws):
        from regian.skills.project import rename_project
        result = rename_project("bestaat_niet", "nieuw")
        assert "❌" in result

    def test_fout_als_nieuw_al_bestaat(self, ws):
        from regian.skills.project import create_project, rename_project
        create_project("proj1", "generic")
        create_project("proj2", "generic")
        result = rename_project("proj1", "proj2")
        assert "❌" in result
        assert (ws / "proj1").is_dir()  # origineel onaangetast

    def test_zelfde_naam_geeft_info(self, ws):
        from regian.skills.project import create_project, rename_project
        create_project("zelfde", "generic")
        result = rename_project("zelfde", "zelfde")
        assert "ℹ️" in result

    def test_lege_naam_geeft_fout(self, ws):
        from regian.skills.project import rename_project
        result = rename_project("", "nieuw")
        assert "❌" in result
